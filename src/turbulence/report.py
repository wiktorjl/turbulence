"""
HTML Report Generator for Turbulence Regime Analysis

Generates self-contained HTML reports with inline CSS and optional
matplotlib charts embedded as base64 PNG images.

Report sections:
1. Executive Summary — current regime, composite score, days since last transition
2. Regime Timeline — table of regime periods with durations
3. Component Scores — latest values for each of the 5 components
4. Regime Statistics — frequency/duration stats per regime
5. Trading Recommendations — guidance based on current regime
"""

import base64
import io
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from turbulence.config import get_logger

logger = get_logger(__name__)


# --- HTML Template ---

REPORT_CSS = """
body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    max-width: 960px;
    margin: 0 auto;
    padding: 20px;
    color: #333;
    background: #fafafa;
}
h1 { color: #2E4057; border-bottom: 3px solid #2E4057; padding-bottom: 10px; }
h2 { color: #4A6FA5; margin-top: 30px; border-bottom: 1px solid #ddd; padding-bottom: 5px; }
table { border-collapse: collapse; width: 100%; margin: 15px 0; }
th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
th { background: #4A6FA5; color: white; }
tr:nth-child(even) { background: #f2f2f2; }
.regime-low { color: #2E7D32; font-weight: bold; }
.regime-normal { color: #F9A825; font-weight: bold; }
.regime-elevated { color: #E65100; font-weight: bold; }
.regime-extreme { color: #B71C1C; font-weight: bold; }
.summary-box {
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.metric { display: inline-block; margin: 10px 20px 10px 0; }
.metric-value { font-size: 28px; font-weight: bold; color: #2E4057; }
.metric-label { font-size: 13px; color: #666; }
.chart-container { text-align: center; margin: 20px 0; }
.chart-container img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }
.footer { margin-top: 40px; padding-top: 15px; border-top: 1px solid #ddd;
           font-size: 12px; color: #999; text-align: center; }
"""

TRADING_RECOMMENDATIONS = {
    'low': {
        'title': 'Low Turbulence — Calm Markets',
        'position_sizing': 'Full position sizes. Normal risk parameters.',
        'es_futures': 'Support/resistance bounce strategies work well. Standard stop widths.',
        'options': 'Buy cheap OTM puts as portfolio insurance. Consider debit spreads for directional bets.',
        'risk': 'Monitor for complacency. VIX < 15 often precedes vol expansion.',
    },
    'normal': {
        'title': 'Normal Turbulence — Average Conditions',
        'position_sizing': 'Standard position sizes. Balanced approach.',
        'es_futures': 'Mix of mean-reversion and trend-following. Normal S/R zones.',
        'options': 'Balanced premium selling and buying. Iron condors viable.',
        'risk': 'Standard risk management. Watch for regime transitions.',
    },
    'elevated': {
        'title': 'Elevated Turbulence — Heightened Uncertainty',
        'position_sizing': 'Reduce risk 25-50%. Tighter position limits.',
        'es_futures': 'Widen stop losses by 1.5x ATR. Favor momentum/breakout strategies.',
        'options': 'Sell premium via credit spreads (high IV). Avoid naked short puts.',
        'risk': 'Active monitoring required. Prepare for possible escalation to extreme.',
    },
    'extreme': {
        'title': 'Extreme Turbulence — Crisis Conditions',
        'position_sizing': 'Half size or less. Defensive positioning.',
        'es_futures': 'Reduce exposure significantly. Use wider stops (2x normal ATR).',
        'options': 'Only defined-risk spreads. No naked short premium. VIX > 30 spikes resolve in ~3 months.',
        'risk': 'Maximum caution. Consider hedging existing positions with puts or VIX calls.',
    },
}


def _regime_css_class(regime: str) -> str:
    """Return CSS class for a regime label."""
    return f'regime-{regime.lower()}' if regime else ''


def _compute_regime_periods(regime_series: pd.Series) -> pd.DataFrame:
    """
    Compute contiguous regime periods from a regime time series.

    Returns DataFrame with columns: regime, start_date, end_date, duration_days.
    """
    if regime_series.empty:
        return pd.DataFrame(columns=['regime', 'start_date', 'end_date', 'duration_days'])

    periods = []
    current_regime = regime_series.iloc[0]
    period_start = regime_series.index[0]

    for i in range(1, len(regime_series)):
        if regime_series.iloc[i] != current_regime:
            periods.append({
                'regime': current_regime,
                'start_date': period_start,
                'end_date': regime_series.index[i - 1],
                'duration_days': (regime_series.index[i - 1] - period_start).days + 1,
            })
            current_regime = regime_series.iloc[i]
            period_start = regime_series.index[i]

    # Final period
    periods.append({
        'regime': current_regime,
        'start_date': period_start,
        'end_date': regime_series.index[-1],
        'duration_days': (regime_series.index[-1] - period_start).days + 1,
    })

    return pd.DataFrame(periods)


def _generate_composite_chart(dates, scores, regimes) -> Optional[str]:
    """
    Generate composite score chart as base64-encoded PNG.

    Returns base64 string or None if matplotlib unavailable.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except ImportError:
        logger.warning("matplotlib not available, skipping charts")
        return None

    fig, ax = plt.subplots(figsize=(12, 4))

    regime_colors = {
        'low': '#4CAF50',
        'normal': '#FFC107',
        'elevated': '#FF9800',
        'extreme': '#F44336',
    }

    # Background shading by regime
    prev_regime = None
    span_start = dates[0]
    for i, (date, regime) in enumerate(zip(dates, regimes)):
        if regime != prev_regime and prev_regime is not None:
            color = regime_colors.get(str(prev_regime), '#CCCCCC')
            ax.axvspan(span_start, date, facecolor=color, alpha=0.15)
            span_start = date
        prev_regime = regime
    # Final span
    if prev_regime is not None:
        color = regime_colors.get(str(prev_regime), '#CCCCCC')
        ax.axvspan(span_start, dates[-1], facecolor=color, alpha=0.15)

    # Score line
    ax.plot(dates, scores, linewidth=1.5, color='#2E4057')

    # Threshold lines
    for thresh, label in [(0.25, 'Low/Normal'), (0.50, 'Normal/Elevated'), (0.75, 'Elevated/Extreme')]:
        ax.axhline(y=thresh, color='gray', linestyle='--', linewidth=0.7, alpha=0.6)

    ax.set_ylabel('Composite Score')
    ax.set_ylim(0, 1)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    ax.set_title('Turbulence Composite Score')
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def generate_report(
    db,
    start_date: datetime,
    end_date: datetime,
    output_path: str,
    format: str = 'html',
    include_charts: bool = True,
) -> str:
    """
    Generate a turbulence analysis report.

    Parameters
    ----------
    db : DatabaseManager
        Database connection manager.
    start_date : datetime
        Report period start.
    end_date : datetime
        Report period end.
    output_path : str
        Path to write the report file.
    format : str, default 'html'
        Report format. Only 'html' is supported; 'pdf' requires weasyprint.
    include_charts : bool, default True
        Whether to embed matplotlib charts in the report.

    Returns
    -------
    str
        Path to the generated report file.

    Raises
    ------
    ValueError
        If no data found for the specified period or format is unsupported.
    """
    if format == 'pdf':
        try:
            import weasyprint  # noqa: F401
        except ImportError:
            raise ValueError(
                "PDF format requires the 'weasyprint' package. "
                "Install it with: pip install weasyprint"
            )

    logger.info(f"Generating {format.upper()} report for {start_date.date()} to {end_date.date()}")

    # Query composite scores
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT date, composite_score, regime_label,
                       vix_component, realized_vol_component, turbulence_component,
                       garch_component, vix_term_component
                FROM turbulence_composite_scores
                WHERE date >= %s AND date <= %s
                ORDER BY date
            """, (start_date.date(), end_date.date()))
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]

    if not rows:
        raise ValueError(f"No composite score data found between {start_date.date()} and {end_date.date()}")

    df = pd.DataFrame(rows, columns=columns)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')

    # --- Section 1: Executive Summary ---
    latest = df.iloc[-1]
    current_regime = latest['regime_label']
    current_score = latest['composite_score']

    # Days since last transition
    regimes = df['regime_label']
    transitions = regimes != regimes.shift()
    last_transition_idx = transitions[transitions].index[-1] if transitions.any() else regimes.index[0]
    days_since_transition = (df.index[-1] - last_transition_idx).days

    # --- Section 2: Regime Timeline ---
    regime_periods = _compute_regime_periods(df['regime_label'])

    # --- Section 3: Component Scores ---
    component_cols = ['vix_component', 'realized_vol_component', 'turbulence_component',
                      'garch_component', 'vix_term_component']
    component_names = {
        'vix_component': 'VIX Percentile',
        'realized_vol_component': 'Realized Volatility',
        'turbulence_component': 'Turbulence Index',
        'garch_component': 'GARCH Conditional Vol',
        'vix_term_component': 'VIX Term Structure',
    }

    # --- Section 4: Regime Statistics ---
    regime_stats = df['regime_label'].value_counts()
    total_days = len(df)
    regime_stat_rows = []
    for regime in ['low', 'normal', 'elevated', 'extreme']:
        count = regime_stats.get(regime, 0)
        pct = count / total_days if total_days > 0 else 0
        # Average duration from periods
        regime_dur = regime_periods[regime_periods['regime'] == regime]['duration_days']
        avg_dur = regime_dur.mean() if len(regime_dur) > 0 else 0
        regime_stat_rows.append({
            'regime': regime,
            'days': count,
            'pct': pct,
            'num_periods': len(regime_dur),
            'avg_duration': avg_dur,
        })

    # --- Section 5: Trading Recommendations ---
    rec = TRADING_RECOMMENDATIONS.get(current_regime, TRADING_RECOMMENDATIONS['normal'])

    # --- Generate chart ---
    chart_b64 = None
    if include_charts:
        chart_b64 = _generate_composite_chart(
            df.index.tolist(),
            df['composite_score'].tolist(),
            df['regime_label'].tolist(),
        )

    # --- Build HTML ---
    html_parts = []
    html_parts.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Turbulence Analysis Report — {start_date.date()} to {end_date.date()}</title>
<style>{REPORT_CSS}</style>
</head>
<body>
<h1>Turbulence Analysis Report</h1>
<p>Period: {start_date.date()} to {end_date.date()} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
""")

    # Executive Summary
    html_parts.append(f"""
<h2>Executive Summary</h2>
<div class="summary-box">
  <div class="metric">
    <div class="metric-value {_regime_css_class(current_regime)}">{current_regime.upper()}</div>
    <div class="metric-label">Current Regime</div>
  </div>
  <div class="metric">
    <div class="metric-value">{current_score:.3f}</div>
    <div class="metric-label">Composite Score</div>
  </div>
  <div class="metric">
    <div class="metric-value">{days_since_transition}</div>
    <div class="metric-label">Days in Current Regime</div>
  </div>
  <div class="metric">
    <div class="metric-value">{total_days}</div>
    <div class="metric-label">Total Trading Days</div>
  </div>
</div>
""")

    # Chart
    if chart_b64:
        html_parts.append(f"""
<div class="chart-container">
  <img src="data:image/png;base64,{chart_b64}" alt="Turbulence Composite Score Chart">
</div>
""")

    # Regime Timeline (last 20 periods)
    html_parts.append("<h2>Regime Timeline</h2>")
    display_periods = regime_periods.tail(20)
    html_parts.append("<table><tr><th>Regime</th><th>Start</th><th>End</th><th>Duration (days)</th></tr>")
    for _, row in display_periods.iterrows():
        css = _regime_css_class(row['regime'])
        start_str = row['start_date'].strftime('%Y-%m-%d') if hasattr(row['start_date'], 'strftime') else str(row['start_date'])
        end_str = row['end_date'].strftime('%Y-%m-%d') if hasattr(row['end_date'], 'strftime') else str(row['end_date'])
        html_parts.append(
            f"<tr><td class='{css}'>{row['regime'].upper()}</td>"
            f"<td>{start_str}</td><td>{end_str}</td>"
            f"<td>{row['duration_days']}</td></tr>"
        )
    html_parts.append("</table>")

    # Component Scores
    html_parts.append("<h2>Component Scores (Latest)</h2>")
    html_parts.append("<table><tr><th>Component</th><th>Score</th><th>Weight</th></tr>")
    weights = {'vix_component': 0.25, 'realized_vol_component': 0.20, 'turbulence_component': 0.25,
               'garch_component': 0.15, 'vix_term_component': 0.15}
    for col in component_cols:
        val = latest.get(col, None)
        val_str = f"{val:.3f}" if val is not None and not pd.isna(val) else "N/A"
        name = component_names.get(col, col)
        weight = weights.get(col, 0)
        html_parts.append(f"<tr><td>{name}</td><td>{val_str}</td><td>{weight:.0%}</td></tr>")
    html_parts.append("</table>")

    # Regime Statistics
    html_parts.append("<h2>Regime Statistics</h2>")
    html_parts.append("<table><tr><th>Regime</th><th>Days</th><th>% of Period</th>"
                      "<th># Periods</th><th>Avg Duration</th></tr>")
    for row in regime_stat_rows:
        css = _regime_css_class(row['regime'])
        html_parts.append(
            f"<tr><td class='{css}'>{row['regime'].upper()}</td>"
            f"<td>{row['days']}</td><td>{row['pct']:.1%}</td>"
            f"<td>{row['num_periods']}</td><td>{row['avg_duration']:.0f} days</td></tr>"
        )
    html_parts.append("</table>")

    # Trading Recommendations
    html_parts.append(f"<h2>Trading Recommendations — {rec['title']}</h2>")
    html_parts.append("<div class='summary-box'>")
    html_parts.append(f"<p><strong>Position Sizing:</strong> {rec['position_sizing']}</p>")
    html_parts.append(f"<p><strong>ES Futures:</strong> {rec['es_futures']}</p>")
    html_parts.append(f"<p><strong>Options:</strong> {rec['options']}</p>")
    html_parts.append(f"<p><strong>Risk Management:</strong> {rec['risk']}</p>")
    html_parts.append("</div>")

    # Footer
    html_parts.append("""
<div class="footer">
  Generated by Turbulence — Market Regime Detection System
</div>
</body>
</html>""")

    html_content = "\n".join(html_parts)

    if format == 'pdf':
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(output_path)
    else:
        with open(output_path, 'w') as f:
            f.write(html_content)

    logger.info(f"Report written to {output_path}")
    return output_path
