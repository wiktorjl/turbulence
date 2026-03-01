"""
Chart generation for turbulence scores with regime zones.

Generates matplotlib charts showing composite turbulence scores
over time with color-coded regime background zones.
"""

import sys
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch
import pandas as pd

from turbulence import storage


def fetch_turbulence_data(start_date=None, end_date=None):
    """Fetch turbulence scores from parquet storage."""
    df = storage.load_composite_scores(start_date, end_date)

    if df.empty:
        raise ValueError("No data found for specified date range")

    df['date'] = pd.to_datetime(df['date'])
    df['composite_score'] = df['composite_score'].astype(float)

    return df


def plot_turbulence_chart(df, output_file=None):
    """Create a turbulence chart with regime zones."""

    fig, ax = plt.subplots(figsize=(14, 7))

    regime_colors = {
        'low': '#90EE90',
        'normal': '#FFD700',
        'elevated': '#FFA500',
        'extreme': '#FF4500',
    }

    # Color background based on actual regime
    for i in range(len(df) - 1):
        regime = df.iloc[i]['regime_label'].lower()
        color = regime_colors.get(regime, '#CCCCCC')
        ax.axvspan(df.iloc[i]['date'], df.iloc[i + 1]['date'],
                   facecolor=color, alpha=0.2, zorder=0)

    # Color the last segment
    if len(df) > 0:
        regime = df.iloc[-1]['regime_label'].lower()
        color = regime_colors.get(regime, '#CCCCCC')
        last_date = df.iloc[-1]['date']
        extended_date = last_date + pd.Timedelta(days=2)
        ax.axvspan(last_date, extended_date, facecolor=color, alpha=0.2, zorder=0)

    # Plot the turbulence score line
    ax.plot(df['date'], df['composite_score'],
            linewidth=2, color='#2E4057', label='Turbulence Score', zorder=5)

    # Add markers at data points
    ax.scatter(df['date'], df['composite_score'],
               s=20, color='#2E4057', alpha=0.6, zorder=6)

    # Add reference lines at regime boundaries
    regime_thresholds = [
        (0.25, 'Normal entry'),
        (0.50, 'Elevated entry'),
        (0.75, 'Extreme entry')
    ]
    for y, label in regime_thresholds:
        ax.axhline(y=y, color='gray', linestyle='--',
                   linewidth=0.8, alpha=0.3, zorder=1)

    # Set labels and title
    date_range_str = f"{df['date'].min().strftime('%Y-%m-%d')} to {df['date'].max().strftime('%Y-%m-%d')}"

    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Composite Turbulence Score', fontsize=12, fontweight='bold')
    ax.set_title(f'Market Turbulence Regime Detection\n{date_range_str}',
                 fontsize=16, fontweight='bold', pad=20)

    ax.set_ylim(-0.05, 1.05)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45, ha='right')

    ax.grid(True, alpha=0.3, linestyle=':', linewidth=0.5, zorder=0)

    # Custom legend
    legend_elements = [
        Patch(facecolor='#90EE90', alpha=0.5, label='Low: Calm markets, normal trading'),
        Patch(facecolor='#FFD700', alpha=0.5, label='Normal: Average volatility'),
        Patch(facecolor='#FFA500', alpha=0.5, label='Elevated: Reduce risk 25-50%'),
        Patch(facecolor='#FF4500', alpha=0.5, label='Extreme: Crisis mode, stand aside'),
    ]

    ax.legend(handles=legend_elements, loc='upper left',
              framealpha=0.9, fontsize=10, title='Trading Regimes')

    # Current value annotation
    latest = df.iloc[-1]
    score = latest['composite_score']
    regime = latest['regime_label'].upper()

    annotation_text = f"Current: {score:.3f}\nRegime: {regime}"

    if regime == "LOW":
        bg_color = 'lightgreen'
    elif regime == "NORMAL":
        bg_color = 'lightyellow'
    elif regime == "ELEVATED":
        bg_color = 'orange'
    else:
        bg_color = 'red'

    ax.annotate(annotation_text,
                xy=(latest['date'], score),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc=bg_color, alpha=0.8,
                         edgecolor='black', linewidth=2),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0',
                              color='black', lw=2),
                fontsize=11, fontweight='bold', zorder=10)

    # Statistics text box
    stats_text = f"""Statistics:
Mean: {df['composite_score'].mean():.3f}
Std: {df['composite_score'].std():.3f}
Min: {df['composite_score'].min():.3f}
Max: {df['composite_score'].max():.3f}
Days: {len(df)}"""

    ax.text(0.98, 0.02, stats_text, transform=ax.transAxes,
            fontsize=9, verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Chart saved to: {output_file}")
    else:
        plt.show()

    plt.close()


def main():
    """CLI entry point for standalone chart generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate turbulence score chart with regime zones'
    )
    parser.add_argument('--start-date', type=str, default=None,
                       help='Start date (YYYY-MM-DD). Default: start of current year')
    parser.add_argument('--end-date', type=str, default=None,
                       help='End date (YYYY-MM-DD). Default: today')
    parser.add_argument('--output', type=str, default=None,
                       help='Output file path (e.g., turbulence.png). Default: display on screen')
    parser.add_argument('--ytd', action='store_true',
                       help='Show year-to-date (shortcut for --start-date YYYY-01-01)')

    args = parser.parse_args()

    start_date = args.start_date
    end_date = args.end_date

    if args.ytd:
        start_date = f"{datetime.now().year}-01-01"

    if start_date is None:
        start_date = f"{datetime.now().year}-01-01"

    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')

    print(f"Fetching turbulence data from {start_date} to {end_date}...")

    try:
        df = fetch_turbulence_data(start_date, end_date)
        print(f"Found {len(df)} data points")

        print("Generating chart...")
        plot_turbulence_chart(df, args.output)

        print("Done!")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
