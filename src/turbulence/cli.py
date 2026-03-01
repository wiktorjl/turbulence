"""
CLI interface for the Turbulence market regime detection system.

This module provides a command-line interface using Click for managing
data fetching, indicator computation, regime status monitoring, backtesting,
and report generation.
"""

import sys
from datetime import datetime, timedelta
from typing import Optional

import click

from turbulence import __version__
from turbulence import storage


@click.group()
@click.version_option(version=__version__)
@click.pass_context
def main(ctx):
    """
    Turbulence: Market regime detection and turbulence analysis system.

    A comprehensive system for detecting financial market turbulence using
    VIX thresholds, statistical models (HMM, GARCH), and multi-asset
    turbulence indices (Mahalanobis distance).

    Use --help with any command for detailed usage information.
    """
    ctx.ensure_object(dict)


@main.command()
def init():
    """
    Initialize the data directory.

    Creates the directory structure for storing price data and computed results
    as parquet files. Safe to run multiple times.

    Examples:

        turbulence init
    """
    try:
        storage.init_data_dir()
        data_dir = storage.get_data_dir()
        click.echo(f"Data directory initialized at {data_dir}")
        click.echo("\nDirectory structure:")
        click.echo(f"  {data_dir}/prices/     (OHLCV price data)")
        click.echo(f"  {data_dir}/            (computed results)")
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='Start date for data fetch (YYYY-MM-DD). Defaults to 5 years ago.'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='End date for data fetch (YYYY-MM-DD). Defaults to today.'
)
@click.option(
    '--tickers',
    type=str,
    default='SPY,TLT,GLD,UUP,HYG,^VIX,^VIX3M',
    help='Comma-separated list of tickers to fetch. Default: SPY,TLT,GLD,UUP,HYG,^VIX,^VIX3M'
)
def fetch_data(start_date, end_date, tickers):
    """
    Fetch historical market data for specified date range and tickers.

    Downloads OHLCV data from Yahoo Finance and stores it as parquet files.
    Includes support for VIX indices and cross-asset data required for
    turbulence index calculation.

    Examples:

        # Fetch default tickers for last 5 years
        turbulence fetch-data

        # Fetch specific tickers for custom date range
        turbulence fetch-data --start-date 2020-01-01 --end-date 2023-12-31 --tickers SPY,VIX

        # Initialize data dir and fetch data
        turbulence init && turbulence fetch-data
    """
    try:
        # Set default dates if not provided
        if end_date is None:
            end_date = datetime.now()
        if start_date is None:
            start_date = end_date - timedelta(days=5*365)

        ticker_list = [t.strip() for t in tickers.split(',')]

        click.echo(f"Fetching data from {start_date.date()} to {end_date.date()}")
        click.echo(f"Tickers: {', '.join(ticker_list)}")

        # Ensure data directory exists
        storage.init_data_dir()

        from turbulence.data_fetcher import get_data_fetcher

        fetcher = get_data_fetcher()

        total_rows = 0
        for ticker in ticker_list:
            rows = fetcher.fetch_and_store(
                ticker,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d'),
            )
            if rows > 0:
                click.echo(f"  {ticker}: {rows} rows")
                total_rows += rows
            else:
                click.echo(f"  {ticker}: no data fetched", err=True)

        click.echo(f"\nTotal rows stored: {total_rows}")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
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

        # Fetch price data from parquet storage
        tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']
        df = storage.load_all_prices(tickers, start_date, end_date)

        if df.empty:
            click.echo("No price data found. Run 'fetch-data' first.", err=True)
            sys.exit(1)

        # Pivot to get SPY data for main calculations
        spy_data = df[df['ticker'] == 'SPY'].copy()
        if spy_data.empty:
            click.echo("No SPY data found. Cannot compute indicators.", err=True)
            sys.exit(1)

        spy_data = spy_data.sort_values('date').reset_index(drop=True)

        if indicators in ['tier1', 'all']:
            click.echo("Computing Tier 1 indicators...")
            # Get VIX data
            vix_data = df[df['ticker'] == '^VIX'].copy().sort_values('date')
            vix3m_data = df[df['ticker'] == '^VIX3M'].copy().sort_values('date')

            # Merge VIX into SPY data
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

            # Calculate Tier 1 indicators
            spy_data = calculate_tier1_indicators(
                spy_data,
                vix_col='vix',
                vix3m_col='vix3m' if 'vix3m' in spy_data.columns else None
            )
            click.echo("  Tier 1 complete")

        if indicators in ['tier2', 'all']:
            click.echo("Computing Tier 2 models...")
            returns = np.log(spy_data['close'] / spy_data['close'].shift(1))
            spy_data['garch_vol'] = rolling_garch_volatility(returns, window=252, min_periods=100)
            click.echo("  Tier 2 complete (GARCH)")

        if indicators in ['tier3', 'all']:
            click.echo("Computing Tier 3 turbulence...")
            # Build multi-asset returns matrix
            asset_tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG']
            returns_data = []
            for ticker in asset_tickers:
                ticker_df = df[df['ticker'] == ticker].copy().sort_values('date')
                if not ticker_df.empty:
                    ticker_df['returns'] = ticker_df['close'].pct_change()
                    returns_data.append(ticker_df[['date', 'returns']].rename(columns={'returns': ticker}))

            if len(returns_data) >= 3:
                returns_df = returns_data[0]
                for rdf in returns_data[1:]:
                    returns_df = returns_df.merge(rdf, on='date', how='outer')
                returns_df = returns_df.set_index('date').dropna()

                tier3_results = calculate_tier3_indicators(returns_df)
                # Merge back into spy_data
                spy_data = spy_data.merge(
                    pd.DataFrame({
                        'date': tier3_results['turbulence'].index,
                        'turbulence_index': tier3_results['turbulence'].values
                    }),
                    on='date',
                    how='left'
                )
                click.echo("  Tier 3 complete")

        if indicators == 'all':
            click.echo("Computing composite turbulence scores...")
            # Prepare required series for composite scorer
            if all(col in spy_data.columns for col in ['vix', 'vix_term_structure_ratio', 'garman_klass_vol', 'turbulence_index', 'garch_vol']):
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
                # Store component scores
                components_df = result['components']
                for col in components_df.columns:
                    spy_data[col] = components_df[col]
                spy_data = spy_data.reset_index()
                click.echo("  Composite scoring complete")

        # Store results to parquet
        click.echo("\nStoring results...")

        # Build regime classifications DataFrame
        regime_rows = []
        for _, row in spy_data.iterrows():
            if 'vix' in row and pd.notna(row['vix']):
                regime_rows.append({
                    'date': row['date'],
                    'vix_level': float(row['vix']) if pd.notna(row['vix']) else None,
                    'vix3m_level': float(row.get('vix3m')) if 'vix3m' in row and pd.notna(row.get('vix3m')) else None,
                    'vix_term_structure_ratio': float(row.get('vix_term_structure_ratio')) if 'vix_term_structure_ratio' in row and pd.notna(row.get('vix_term_structure_ratio')) else None,
                    'vix_regime': str(row.get('vix_regime')) if 'vix_regime' in row and pd.notna(row.get('vix_regime')) else None,
                })

        if regime_rows:
            regime_df = pd.DataFrame(regime_rows)
            storage.save_regime_classifications(regime_df)

        # Build composite scores DataFrame
        composite_rows = []
        for _, row in spy_data.iterrows():
            if 'composite_score' in row and pd.notna(row.get('composite_score')):
                composite_rows.append({
                    'date': row['date'],
                    'composite_score': float(row['composite_score']),
                    'regime_label': str(row.get('regime')),
                    'vix_component': float(row.get('vix_percentile')) if 'vix_percentile' in row and pd.notna(row.get('vix_percentile')) else None,
                    'vix_term_component': float(row.get('vix_term_structure')) if 'vix_term_structure' in row and pd.notna(row.get('vix_term_structure')) else None,
                    'realized_vol_component': float(row.get('realized_vol_percentile')) if 'realized_vol_percentile' in row and pd.notna(row.get('realized_vol_percentile')) else None,
                    'turbulence_component': float(row.get('turbulence_percentile')) if 'turbulence_percentile' in row and pd.notna(row.get('turbulence_percentile')) else None,
                    'garch_component': float(row.get('garch_vol_percentile')) if 'garch_vol_percentile' in row and pd.notna(row.get('garch_vol_percentile')) else None,
                })

        stored_count = len(composite_rows)
        if composite_rows:
            composite_df = pd.DataFrame(composite_rows)
            storage.save_composite_scores(composite_df)

        click.echo(f"  Stored {stored_count} regime records")
        click.echo(f"\nComputation complete. Processed {len(spy_data)} days of data.")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    '--date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='Date to check status for (YYYY-MM-DD). Defaults to latest available.'
)
@click.option(
    '--format',
    type=click.Choice(['table', 'json'], case_sensitive=False),
    default='table',
    help='Output format. Default: table'
)
@click.option(
    '--detailed',
    is_flag=True,
    help='Show detailed component scores and probabilities.'
)
def status(date, format, detailed):
    """
    Display current market regime and component turbulence scores.

    Shows the composite turbulence score, regime classification, and
    optionally detailed breakdowns of all component indicators including
    VIX levels, HMM regime probabilities, turbulence index, and more.

    Examples:

        # Show current market regime
        turbulence status

        # Show detailed status for specific date
        turbulence status --date 2024-03-15 --detailed

        # Export status as JSON
        turbulence status --format json
    """
    try:
        import pandas as pd
        import json

        if date is None:
            date_str = "latest available"
        else:
            date_str = date.date()

        click.echo(f"Market Regime Status as of {date_str}")
        click.echo("=" * 60)

        # Load composite scores
        composite_df = storage.load_composite_scores()
        regime_df = storage.load_regime_classifications()

        composite_row = None
        regime_row = None

        if not composite_df.empty:
            composite_df['date'] = pd.to_datetime(composite_df['date'])
            if date is not None:
                mask = composite_df['date'].dt.date == date.date()
                matched = composite_df[mask]
                if not matched.empty:
                    composite_row = matched.iloc[-1]
            else:
                composite_row = composite_df.iloc[-1]

        if not regime_df.empty:
            regime_df['date'] = pd.to_datetime(regime_df['date'])
            if date is not None:
                mask = regime_df['date'].dt.date == date.date()
                matched = regime_df[mask]
                if not matched.empty:
                    regime_row = matched.iloc[-1]
            else:
                regime_row = regime_df.iloc[-1]

        if composite_row is None and regime_row is None:
            if date is not None:
                click.echo(f"No regime data found for {date_str}.", err=True)
                click.echo("Try a different date or run 'compute' to generate data.", err=True)
            else:
                click.echo("No regime data found. Run 'compute' first.", err=True)
            sys.exit(1)

        if format == 'table':
            if composite_row is not None:
                comp_score = composite_row.get('composite_score')
                regime_label = composite_row.get('regime_label')
                comp_date = composite_row.get('date')
                click.echo(f"\nComposite Turbulence Score: {comp_score:.3f}" if comp_score else "\nComposite Turbulence Score: --")
                click.echo(f"Current Regime: {regime_label.upper()}" if regime_label else "Current Regime: --")
                click.echo(f"As of: {comp_date}")
            else:
                click.echo("\nComposite Turbulence Score: --")
                click.echo("Current Regime: (not computed)")

            click.echo("\nRegime Interpretation:")
            click.echo("  Low (0.00-0.25):      Calm markets, normal trading")
            click.echo("  Normal (0.25-0.50):   Average volatility")
            click.echo("  Elevated (0.50-0.75): Heightened uncertainty, reduce risk")
            click.echo("  Extreme (0.75-1.00):  Crisis conditions, defensive positioning")

            if detailed:
                click.echo("\nComponent Scores:")
                if composite_row is not None:
                    vix_comp = composite_row.get('vix_component')
                    vix_term_comp = composite_row.get('vix_term_component')
                    real_vol_comp = composite_row.get('realized_vol_component')
                    turb_comp = composite_row.get('turbulence_component')
                    garch_comp = composite_row.get('garch_component')
                    click.echo(f"  VIX Component:              {vix_comp:.3f}" if vix_comp and pd.notna(vix_comp) else "  VIX Component:              --")
                    click.echo(f"  VIX Term Structure:         {vix_term_comp:.3f}" if vix_term_comp and pd.notna(vix_term_comp) else "  VIX Term Structure:         --")
                    click.echo(f"  Realized Volatility:        {real_vol_comp:.3f}" if real_vol_comp and pd.notna(real_vol_comp) else "  Realized Volatility:        --")
                    click.echo(f"  Turbulence Index:           {turb_comp:.3f}" if turb_comp and pd.notna(turb_comp) else "  Turbulence Index:           --")
                    click.echo(f"  GARCH Conditional Vol:      {garch_comp:.3f}" if garch_comp and pd.notna(garch_comp) else "  GARCH Conditional Vol:      --")

                if regime_row is not None:
                    vix_level = regime_row.get('vix_level')
                    vix_regime = regime_row.get('vix_regime')
                    vix_term_ratio = regime_row.get('vix_term_structure_ratio')
                    click.echo("\nVIX Data:")
                    click.echo(f"  VIX Level:                  {vix_level:.2f}" if vix_level and pd.notna(vix_level) else "  VIX Level:                  --")
                    click.echo(f"  VIX Regime:                 {vix_regime}" if vix_regime and pd.notna(vix_regime) else "  VIX Regime:                 --")
                    click.echo(f"  VIX/VIX3M Ratio:            {vix_term_ratio:.3f}" if vix_term_ratio and pd.notna(vix_term_ratio) else "  VIX/VIX3M Ratio:            --")

        elif format == 'json':
            result = {
                "composite_score": float(composite_row['composite_score']) if composite_row is not None and pd.notna(composite_row.get('composite_score')) else None,
                "regime": composite_row['regime_label'] if composite_row is not None else None,
                "date": str(composite_row['date']) if composite_row is not None else None,
                "components": {
                    "vix": float(composite_row['vix_component']) if composite_row is not None and pd.notna(composite_row.get('vix_component')) else None,
                    "vix_term": float(composite_row['vix_term_component']) if composite_row is not None and pd.notna(composite_row.get('vix_term_component')) else None,
                    "realized_vol": float(composite_row['realized_vol_component']) if composite_row is not None and pd.notna(composite_row.get('realized_vol_component')) else None,
                    "turbulence": float(composite_row['turbulence_component']) if composite_row is not None and pd.notna(composite_row.get('turbulence_component')) else None,
                    "garch": float(composite_row['garch_component']) if composite_row is not None and pd.notna(composite_row.get('garch_component')) else None,
                }
            }
            click.echo(json.dumps(result, indent=2))

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    required=True,
    help='Start date for backtest period (YYYY-MM-DD).'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='End date for backtest period (YYYY-MM-DD). Defaults to today.'
)
@click.option(
    '--train-window',
    type=int,
    default=756,
    help='Training window in days (default: 756 = 3 years).'
)
@click.option(
    '--test-window',
    type=int,
    default=126,
    help='Test window in days (default: 126 = 6 months).'
)
@click.option(
    '--step-size',
    type=int,
    default=63,
    help='Step size for walk-forward (default: 63 = 3 months).'
)
@click.option(
    '--output',
    type=click.Path(),
    default=None,
    help='Output file path for backtest results (CSV format).'
)
def backtest(start_date, end_date, train_window, test_window, step_size, output):
    """
    Run walk-forward validation backtest on historical data.

    Implements proper walk-forward optimization to avoid look-ahead bias.
    Trains models on a rolling window, tests on out-of-sample data,
    and steps forward to simulate realistic regime detection.

    Examples:

        # Run standard 3-year train / 6-month test backtest
        turbulence backtest --start-date 2015-01-01 --end-date 2023-12-31

        # Custom walk-forward parameters
        turbulence backtest --start-date 2015-01-01 --train-window 500 --test-window 100

        # Save results to file
        turbulence backtest --start-date 2015-01-01 --output backtest_results.csv
    """
    try:
        if end_date is None:
            end_date = datetime.now()

        click.echo("Walk-Forward Backtest Configuration")
        click.echo("=" * 60)
        click.echo(f"Period: {start_date.date()} to {end_date.date()}")
        click.echo(f"Training window: {train_window} days")
        click.echo(f"Test window: {test_window} days")
        click.echo(f"Step size: {step_size} days")
        click.echo()

        # Calculate number of iterations
        total_days = (end_date - start_date).days
        available_days = total_days - train_window
        num_iterations = max(0, (available_days - test_window) // step_size + 1)

        click.echo(f"Estimated iterations: {num_iterations}")

        if num_iterations < 1:
            click.echo("Error: Insufficient data for walk-forward validation.", err=True)
            click.echo(f"Need at least {train_window + test_window} days of data.", err=True)
            sys.exit(1)

        # Load price data from parquet
        import pandas as pd

        tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']
        all_prices = storage.load_all_prices(tickers, start_date, end_date)

        if all_prices.empty:
            click.echo("Error: No price data found for the specified period.", err=True)
            click.echo("Run 'turbulence fetch-data' first.", err=True)
            sys.exit(1)

        all_prices['date'] = pd.to_datetime(all_prices['date'])

        # Build price_data (SPY OHLCV + VIX columns)
        spy = all_prices[all_prices['ticker'] == 'SPY'].set_index('date').sort_index()
        vix = all_prices[all_prices['ticker'] == '^VIX'].set_index('date')['close'].rename('vix')
        vix3m = all_prices[all_prices['ticker'] == '^VIX3M'].set_index('date')['close'].rename('vix3m')

        price_data = spy[['open', 'high', 'low', 'close', 'volume']].copy()
        price_data = price_data.join(vix).join(vix3m)
        price_data = price_data.dropna(subset=['close'])

        # Build returns_data for Tier 3
        asset_tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG']
        returns_frames = {}
        for ticker in asset_tickers:
            t_data = all_prices[all_prices['ticker'] == ticker].set_index('date')['close']
            if not t_data.empty:
                returns_frames[ticker] = t_data.pct_change()
        returns_data = pd.DataFrame(returns_frames).dropna()

        if len(price_data) < train_window + test_window:
            click.echo(f"Error: Only {len(price_data)} days of data, need at least {train_window + test_window}.", err=True)
            sys.exit(1)

        click.echo(f"\nLoaded {len(price_data)} days of price data.")
        click.echo("Running walk-forward validation...")

        from turbulence.backtest import run_walk_forward, summarize_backtest

        with click.progressbar(length=num_iterations, label='Progress') as bar:
            iteration_count = [0]
            def update_bar(current, total):
                delta = current - iteration_count[0]
                if delta > 0:
                    bar.update(delta)
                    iteration_count[0] = current

            results = run_walk_forward(
                price_data=price_data,
                returns_data=returns_data,
                start_date=pd.Timestamp(start_date),
                end_date=pd.Timestamp(end_date),
                train_window=train_window,
                test_window=test_window,
                step_size=step_size,
                progress_callback=update_bar,
            )

        if results.empty:
            click.echo("\nNo results produced. Check that data covers the specified period.")
        else:
            click.echo()
            click.echo(summarize_backtest(results))

            if output:
                results.to_csv(output, index=False)
                click.echo(f"\nResults saved to: {output}")

        click.echo("\nBacktest complete.")

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
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


@main.command()
@click.option(
    '--start-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='Start date for chart (YYYY-MM-DD). Default: YTD'
)
@click.option(
    '--end-date',
    type=click.DateTime(formats=['%Y-%m-%d']),
    default=None,
    help='End date for chart (YYYY-MM-DD). Default: today'
)
@click.option(
    '--ytd',
    is_flag=True,
    help='Show year-to-date chart (from Jan 1 to today)'
)
@click.option(
    '--last-3m',
    'last_3m',
    is_flag=True,
    help='Show last 3 months chart'
)
@click.option(
    '--last-6m',
    'last_6m',
    is_flag=True,
    help='Show last 6 months chart'
)
@click.option(
    '--output',
    type=click.Path(),
    default=None,
    help='Output file path (e.g., turbulence.png). Default: display on screen'
)
def chart(start_date, end_date, ytd, last_3m, last_6m, output):
    """
    Generate turbulence score chart with regime zones.

    Creates a visual chart showing the composite turbulence score over time
    with color-coded regime zones (Low, Normal, Elevated, Extreme).

    Examples:

        # Show YTD chart
        turbulence chart --ytd

        # Show last 3 months
        turbulence chart --last-3m

        # Custom date range
        turbulence chart --start-date 2024-01-01 --end-date 2024-12-31

        # Save to file
        turbulence chart --ytd --output turbulence_ytd.png
    """
    try:
        from turbulence.plotting import fetch_turbulence_data, plot_turbulence_chart

        # Determine date range
        if last_3m:
            start = datetime.now() - timedelta(days=90)
            start_date = start.strftime('%Y-%m-%d')
            if not output:
                output = "turbulence_3months.png"
        elif last_6m:
            start = datetime.now() - timedelta(days=180)
            start_date = start.strftime('%Y-%m-%d')
            if not output:
                output = "turbulence_6months.png"
        elif ytd or (start_date is None and end_date is None):
            start_date = f"{datetime.now().year}-01-01"
            if not output:
                output = f"turbulence_ytd_{datetime.now().year}.png"
        else:
            if start_date:
                start_date = start_date.strftime('%Y-%m-%d')
            if end_date:
                end_date = end_date.strftime('%Y-%m-%d')

        click.echo(f"Generating chart from {start_date or 'earliest'} to {end_date or 'today'}...")

        df = fetch_turbulence_data(start_date, end_date)
        click.echo(f"Found {len(df)} data points")

        plot_turbulence_chart(df, output)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
