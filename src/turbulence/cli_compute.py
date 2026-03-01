"""
CLI commands for computing turbulence indicators and generating reports.

Provides the `compute` and `report` subcommands for the turbulence CLI.
"""

import sys
from datetime import datetime, timedelta

import click

from turbulence import storage


def _build_returns_matrix(df, asset_tickers):
    """
    Build a multi-asset returns matrix from long-format price data.

    Pivots per-ticker close prices into a wide DataFrame of daily returns,
    aligned on date with NaN rows dropped.

    Parameters
    ----------
    df : pd.DataFrame
        Long-format price data with 'ticker', 'date', 'close' columns.
    asset_tickers : list[str]
        Tickers to include in the returns matrix.

    Returns
    -------
    pd.DataFrame or None
        Wide-format returns with tickers as columns, dates as index.
        Returns None if fewer than 3 tickers have data.
    """
    import pandas as pd

    returns_data = []
    for ticker in asset_tickers:
        ticker_df = df[df['ticker'] == ticker].copy().sort_values('date')
        if not ticker_df.empty:
            ticker_df['returns'] = ticker_df['close'].pct_change()
            returns_data.append(
                ticker_df[['date', 'returns']].rename(columns={'returns': ticker})
            )

    if len(returns_data) < 3:
        return None

    returns_df = returns_data[0]
    for rdf in returns_data[1:]:
        returns_df = returns_df.merge(rdf, on='date', how='outer')
    return returns_df.set_index('date').dropna()


def _build_regime_df(spy_data):
    """
    Build regime classifications DataFrame from computed spy_data using
    vectorized column selection instead of row-by-row iteration.

    Parameters
    ----------
    spy_data : pd.DataFrame
        SPY data with computed indicators.

    Returns
    -------
    pd.DataFrame or None
        Regime classification records, or None if no VIX data present.
    """
    import pandas as pd

    if 'vix' not in spy_data.columns:
        return None

    # Select rows that have valid VIX data
    mask = spy_data['vix'].notna()
    regime_df = spy_data.loc[mask, ['date']].copy()
    regime_df['vix_level'] = spy_data.loc[mask, 'vix'].astype(float)

    # Optional columns — include if present and not all-NaN
    for src, dst in [
        ('vix3m', 'vix3m_level'),
        ('vix_term_structure_ratio', 'vix_term_structure_ratio'),
        ('vix_regime', 'vix_regime'),
    ]:
        if src in spy_data.columns:
            regime_df[dst] = spy_data.loc[mask, src]

    if 'vix_regime' in regime_df.columns:
        regime_df['vix_regime'] = regime_df['vix_regime'].astype(str)

    return regime_df if not regime_df.empty else None


def _build_composite_df(spy_data):
    """
    Build composite scores DataFrame from computed spy_data using
    vectorized column selection instead of row-by-row iteration.

    Parameters
    ----------
    spy_data : pd.DataFrame
        SPY data with composite scores and component columns.

    Returns
    -------
    pd.DataFrame or None
        Composite score records, or None if no composite data present.
    """
    import pandas as pd

    if 'composite_score' not in spy_data.columns:
        return None

    mask = spy_data['composite_score'].notna()
    comp_df = spy_data.loc[mask, ['date']].copy()
    comp_df['composite_score'] = spy_data.loc[mask, 'composite_score'].astype(float)
    comp_df['regime_label'] = spy_data.loc[mask, 'regime'].astype(str)

    # Map component columns: source name in spy_data -> output column name
    component_map = {
        'vix_percentile': 'vix_component',
        'vix_term_structure': 'vix_term_component',
        'realized_vol_percentile': 'realized_vol_component',
        'turbulence_percentile': 'turbulence_component',
        'garch_vol_percentile': 'garch_component',
    }
    for src, dst in component_map.items():
        if src in spy_data.columns:
            comp_df[dst] = spy_data.loc[mask, src].astype(float)

    return comp_df if not comp_df.empty else None


@click.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='Start date for computation (YYYY-MM-DD). If not specified, computes for all available data.'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='End date for computation (YYYY-MM-DD). Defaults to today.'
)
@click.option(
    '--indicators',
    type=click.Choice(['tier1', 'tier2', 'tier3', 'all'], case_sensitive=False),
    default='all',
    help='Which indicator tiers to compute. Default: all'
)
@click.option(
    '--retrain',
    is_flag=True,
    help='Retrain statistical models (HMM, GARCH) before computing.'
)
def compute(start_date, end_date, indicators, retrain):
    """
    Calculate all turbulence indicators and store results.

    Computes indicators across three tiers:
    - Tier 1: VIX regime, Garman-Klass volatility, volatility percentiles
    - Tier 2: HMM states, GARCH conditional volatility, regime probabilities
    - Tier 3: Mahalanobis turbulence index, absorption ratio

    Also computes composite turbulence scores and regime classifications.

    Examples:

        # Compute all indicators for all available data
        turbulence compute

        # Compute only Tier 1 indicators for recent data
        turbulence compute --start-date 2024-01-01 --indicators tier1

        # Retrain models and compute all indicators
        turbulence compute --retrain
    """
    try:
        if end_date is None:
            end_date = datetime.now()

        click.echo(f"Computing {indicators} indicators...")
        if start_date:
            click.echo(f"Date range: {start_date.date()} to {end_date.date()}")
        else:
            click.echo(f"Computing for all available data through {end_date.date()}")

        if retrain:
            click.echo("Retraining statistical models...")

        import pandas as pd
        import numpy as np
        from turbulence.tier1 import calculate_tier1_indicators
        from turbulence.tier2 import rolling_garch_volatility
        from turbulence.tier3 import calculate_tier3_indicators
        from turbulence.composite import CompositeScorer

        # --- Load price data from parquet ---
        tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']
        df = storage.load_all_prices(tickers, start_date, end_date)

        if df.empty:
            click.echo("No price data found. Run 'fetch-data' first.", err=True)
            sys.exit(1)

        spy_data = df[df['ticker'] == 'SPY'].copy()
        if spy_data.empty:
            click.echo("No SPY data found. Cannot compute indicators.", err=True)
            sys.exit(1)

        spy_data = spy_data.sort_values('date').reset_index(drop=True)

        # --- Tier 1: VIX regime, term structure, Garman-Klass volatility ---
        if indicators in ['tier1', 'all']:
            click.echo("Computing Tier 1 indicators...")
            vix_data = df[df['ticker'] == '^VIX'].copy().sort_values('date')
            vix3m_data = df[df['ticker'] == '^VIX3M'].copy().sort_values('date')

            # Merge VIX spot and 3-month into SPY data for tier1 calculations
            spy_data = spy_data.merge(
                vix_data[['date', 'close']].rename(columns={'close': 'vix'}),
                on='date',
                how='left'
            )
            if not vix3m_data.empty:
                spy_data = spy_data.merge(
                    vix3m_data[['date', 'close']].rename(columns={'close': 'vix3m'}),
                    on='date',
                    how='left'
                )

            spy_data = calculate_tier1_indicators(
                spy_data,
                vix_col='vix',
                vix3m_col='vix3m' if 'vix3m' in spy_data.columns else None
            )
            click.echo("  Tier 1 complete")

        # --- Tier 2: GARCH conditional volatility ---
        if indicators in ['tier2', 'all']:
            click.echo("Computing Tier 2 models...")
            returns = np.log(spy_data['close'] / spy_data['close'].shift(1))
            spy_data['garch_vol'] = rolling_garch_volatility(returns, window=252, min_periods=100)
            click.echo("  Tier 2 complete (GARCH)")

        # --- Tier 3: Mahalanobis turbulence, absorption ratio, GMM clustering ---
        if indicators in ['tier3', 'all']:
            click.echo("Computing Tier 3 turbulence...")
            returns_df = _build_returns_matrix(df, ['SPY', 'TLT', 'GLD', 'UUP', 'HYG'])

            if returns_df is not None:
                tier3_results = calculate_tier3_indicators(returns_df)
                # Merge turbulence index back into spy_data by date
                spy_data = spy_data.merge(
                    pd.DataFrame({
                        'date': tier3_results['turbulence'].index,
                        'turbulence_index': tier3_results['turbulence'].values
                    }),
                    on='date',
                    how='left'
                )
                click.echo("  Tier 3 complete")

        # --- Composite scoring: combine all tiers into single regime score ---
        if indicators == 'all':
            click.echo("Computing composite turbulence scores...")
            required_cols = ['vix', 'vix_term_structure_ratio', 'garman_klass_vol',
                             'turbulence_index', 'garch_vol']
            if all(col in spy_data.columns for col in required_cols):
                spy_data = spy_data.set_index('date')
                scorer = CompositeScorer()
                result = scorer.calculate(
                    vix=spy_data['vix'],
                    vix_term_ratio=spy_data['vix_term_structure_ratio'],
                    realized_vol=spy_data['garman_klass_vol'],
                    turbulence_index=spy_data['turbulence_index'],
                    garch_vol=spy_data['garch_vol']
                )
                spy_data['composite_score'] = result['composite_score']
                spy_data['regime'] = result['regime']
                # Store individual component percentile scores
                components_df = result['components']
                for col in components_df.columns:
                    spy_data[col] = components_df[col]
                spy_data = spy_data.reset_index()
                click.echo("  Composite scoring complete")

        # --- Persist results to parquet ---
        click.echo("\nStoring results...")

        regime_df = _build_regime_df(spy_data)
        if regime_df is not None:
            storage.save_regime_classifications(regime_df)

        composite_df = _build_composite_df(spy_data)
        stored_count = len(composite_df) if composite_df is not None else 0
        if composite_df is not None:
            storage.save_composite_scores(composite_df)

        click.echo(f"  Stored {stored_count} regime records")
        click.echo(f"\nComputation complete. Processed {len(spy_data)} days of data.")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@click.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='Start date for report period (YYYY-MM-DD). Defaults to 1 year ago.'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='End date for report period (YYYY-MM-DD). Defaults to today.'
)
@click.option(
    '--output',
    type=click.Path(),
    required=True,
    help='Output file path for the report (HTML or PDF).'
)
@click.option(
    '--format',
    type=click.Choice(['html', 'pdf'], case_sensitive=False),
    default='html',
    help='Report format. Default: html'
)
@click.option(
    '--include-charts',
    is_flag=True,
    default=True,
    help='Include visualizations in the report.'
)
def report(start_date, end_date, output, format, include_charts):
    """
    Generate comprehensive turbulence analysis report.

    Creates a detailed report including:
    - Time series of all turbulence indicators
    - Regime transition timeline
    - Component score decomposition
    - Historical regime statistics
    - Trading recommendations based on current regime

    Examples:

        # Generate HTML report for last year
        turbulence report --output turbulence_report.html

        # Generate PDF report for custom period
        turbulence report --start-date 2020-01-01 --end-date 2023-12-31 --output report.pdf --format pdf

        # Generate report without charts (faster)
        turbulence report --output report.html --no-include-charts
    """
    try:
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=365)

        click.echo("Generating Turbulence Analysis Report")
        click.echo("=" * 60)
        click.echo(f"Period: {start_date.date()} to {end_date.date()}")
        click.echo(f"Format: {format.upper()}")
        click.echo(f"Output: {output}")
        click.echo(f"Include charts: {include_charts}")
        click.echo()

        from turbulence.report import generate_report

        output_path = generate_report(
            start_date=start_date,
            end_date=end_date,
            output_path=output,
            format=format,
            include_charts=include_charts,
        )

        click.echo(f"\nReport saved to: {output_path}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)
