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
from turbulence.database import get_db_manager


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
@click.option(
    '--init-db',
    is_flag=True,
    help='Initialize database schema before fetching data.'
)
def fetch_data(start_date, end_date, tickers, init_db):
    """
    Fetch historical market data for specified date range and tickers.

    Downloads OHLCV data from Yahoo Finance and stores it in the database.
    Includes support for VIX indices and cross-asset data required for
    turbulence index calculation.

    Examples:

        # Fetch default tickers for last 5 years
        turbulence fetch-data

        # Fetch specific tickers for custom date range
        turbulence fetch-data --start-date 2020-01-01 --end-date 2023-12-31 --tickers SPY,VIX

        # Initialize database and fetch data
        turbulence fetch-data --init-db
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

        db = get_db_manager()

        if init_db:
            click.echo("Initializing database schema...")
            db.create_schema()
            click.echo("Database initialized successfully.")

        # Fetch and store data
        from turbulence.data_fetcher import get_data_fetcher

        fetcher = get_data_fetcher()

        with db.get_connection() as conn:
            result = fetcher.fetch_and_store(
                conn,
                ticker_list,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

        if result['status'] == 'success':
            click.echo(f"✓ Successfully fetched {result['tickers']} tickers")
            click.echo(f"  Total rows: {result['total_rows']}")
            click.echo(f"  Inserted: {result['inserted']}, Updated: {result['updated']}")
            click.echo(f"  Date range: {result['date_range']}")
        else:
            click.echo(f"✗ Error: {result.get('message', 'Unknown error')}", err=True)

        db.close()

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
    Calculate all turbulence indicators and store results in database.

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

        db = get_db_manager()

        import pandas as pd
        import numpy as np
        from turbulence.tier1 import calculate_tier1_indicators
        from turbulence.tier2 import rolling_garch_volatility
        from turbulence.tier3 import calculate_tier3_indicators
        from turbulence.composite import CompositeScorer

        # Fetch price data from database
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT ticker, date, open, high, low, close, volume
                    FROM stock_prices
                    WHERE ticker IN ('SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M')
                    ORDER BY ticker, date
                """
                cur.execute(query)
                rows = cur.fetchall()

        if not rows:
            click.echo("✗ No price data found in database. Run 'fetch-data' first.", err=True)
            sys.exit(1)

        # Convert to DataFrame and ensure numeric types
        df = pd.DataFrame(rows, columns=['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'])
        for col in ['open', 'high', 'low', 'close']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Pivot to get SPY data for main calculations
        spy_data = df[df['ticker'] == 'SPY'].copy()
        if spy_data.empty:
            click.echo("✗ No SPY data found. Cannot compute indicators.", err=True)
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
            click.echo("  ✓ Tier 1 complete")

        if indicators in ['tier2', 'all']:
            click.echo("Computing Tier 2 models...")
            returns = np.log(spy_data['close'] / spy_data['close'].shift(1))
            spy_data['garch_vol'] = rolling_garch_volatility(returns, window=252, min_periods=100)
            click.echo("  ✓ Tier 2 complete (GARCH)")

        if indicators in ['tier3', 'all']:
            click.echo("Computing Tier 3 turbulence...")
            # Build multi-asset returns matrix
            tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG']
            returns_data = []
            for ticker in tickers:
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
                click.echo("  ✓ Tier 3 complete")

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
                click.echo("  ✓ Composite scoring complete")

        # Store results to database
        click.echo("\nStoring results to database...")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                stored_count = 0
                for _, row in spy_data.iterrows():
                    # Store regime classifications
                    if 'vix' in row and pd.notna(row['vix']):
                        cur.execute("""
                            INSERT INTO turbulence_regime_classifications
                            (date, vix_level, vix3m_level, vix_term_structure_ratio, vix_regime)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (date) DO UPDATE SET
                                vix_level = EXCLUDED.vix_level,
                                vix3m_level = EXCLUDED.vix3m_level,
                                vix_term_structure_ratio = EXCLUDED.vix_term_structure_ratio,
                                vix_regime = EXCLUDED.vix_regime
                        """, (
                            row['date'],
                            float(row['vix']) if pd.notna(row['vix']) else None,
                            float(row.get('vix3m')) if 'vix3m' in row and pd.notna(row.get('vix3m')) else None,
                            float(row.get('vix_term_structure_ratio')) if 'vix_term_structure_ratio' in row and pd.notna(row.get('vix_term_structure_ratio')) else None,
                            str(row.get('vix_regime')) if 'vix_regime' in row and pd.notna(row.get('vix_regime')) else None
                        ))

                    # Store composite scores if available
                    if 'composite_score' in row and pd.notna(row.get('composite_score')):
                        cur.execute("""
                            INSERT INTO turbulence_composite_scores
                            (date, composite_score, regime_label,
                             vix_component, vix_term_component, realized_vol_component,
                             turbulence_component, garch_component)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (date) DO UPDATE SET
                                composite_score = EXCLUDED.composite_score,
                                regime_label = EXCLUDED.regime_label,
                                vix_component = EXCLUDED.vix_component,
                                vix_term_component = EXCLUDED.vix_term_component,
                                realized_vol_component = EXCLUDED.realized_vol_component,
                                turbulence_component = EXCLUDED.turbulence_component,
                                garch_component = EXCLUDED.garch_component
                        """, (
                            row['date'],
                            float(row['composite_score']),
                            str(row.get('regime')),
                            float(row.get('vix_percentile')) if 'vix_percentile' in row and pd.notna(row.get('vix_percentile')) else None,
                            float(row.get('vix_term_structure')) if 'vix_term_structure' in row and pd.notna(row.get('vix_term_structure')) else None,
                            float(row.get('realized_vol_percentile')) if 'realized_vol_percentile' in row and pd.notna(row.get('realized_vol_percentile')) else None,
                            float(row.get('turbulence_percentile')) if 'turbulence_percentile' in row and pd.notna(row.get('turbulence_percentile')) else None,
                            float(row.get('garch_vol_percentile')) if 'garch_vol_percentile' in row and pd.notna(row.get('garch_vol_percentile')) else None
                        ))
                        stored_count += 1

        click.echo(f"  ✓ Stored {stored_count} regime records")
        click.echo(f"\n✓ Computation complete. Processed {len(spy_data)} days of data.")
        db.close()

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
        if date is None:
            date_str = "latest available"
        else:
            date_str = date.date()

        click.echo(f"Market Regime Status as of {date_str}")
        click.echo("=" * 60)

        db = get_db_manager()

        import pandas as pd
        import json

        # Query regime data from database (for specific date or latest)
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                if date is not None:
                    # Query for specific date
                    date_filter = date.date()

                    cur.execute("""
                        SELECT date, composite_score, regime_label,
                               vix_component, vix_term_component, realized_vol_component,
                               turbulence_component, garch_component
                        FROM turbulence_composite_scores
                        WHERE date = %s
                    """, (date_filter,))
                    composite_row = cur.fetchone()

                    cur.execute("""
                        SELECT date, vix_level, vix_regime, vix_term_structure_ratio
                        FROM turbulence_regime_classifications
                        WHERE date = %s
                    """, (date_filter,))
                    regime_row = cur.fetchone()
                else:
                    # Query latest available
                    cur.execute("""
                        SELECT date, composite_score, regime_label,
                               vix_component, vix_term_component, realized_vol_component,
                               turbulence_component, garch_component
                        FROM turbulence_composite_scores
                        ORDER BY date DESC
                        LIMIT 1
                    """)
                    composite_row = cur.fetchone()

                    cur.execute("""
                        SELECT date, vix_level, vix_regime, vix_term_structure_ratio
                        FROM turbulence_regime_classifications
                        ORDER BY date DESC
                        LIMIT 1
                    """)
                    regime_row = cur.fetchone()

        if not composite_row and not regime_row:
            if date is not None:
                click.echo(f"✗ No regime data found for {date_str}.", err=True)
                click.echo("Try a different date or run 'compute' to generate data.", err=True)
            else:
                click.echo("✗ No regime data found. Run 'compute' first.", err=True)
            db.close()
            sys.exit(1)

        if format == 'table':
            if composite_row:
                comp_date, comp_score, regime_label, vix_comp, vix_term_comp, real_vol_comp, turb_comp, garch_comp = composite_row
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
                if composite_row:
                    click.echo(f"  VIX Component:              {vix_comp:.3f}" if vix_comp else "  VIX Component:              --")
                    click.echo(f"  VIX Term Structure:         {vix_term_comp:.3f}" if vix_term_comp else "  VIX Term Structure:         --")
                    click.echo(f"  Realized Volatility:        {real_vol_comp:.3f}" if real_vol_comp else "  Realized Volatility:        --")
                    click.echo(f"  Turbulence Index:           {turb_comp:.3f}" if turb_comp else "  Turbulence Index:           --")
                    click.echo(f"  GARCH Conditional Vol:      {garch_comp:.3f}" if garch_comp else "  GARCH Conditional Vol:      --")

                if regime_row:
                    reg_date, vix_level, vix_regime, vix_term_ratio = regime_row
                    click.echo("\nVIX Data:")
                    click.echo(f"  VIX Level:                  {vix_level:.2f}" if vix_level else "  VIX Level:                  --")
                    click.echo(f"  VIX Regime:                 {vix_regime}" if vix_regime else "  VIX Regime:                 --")
                    click.echo(f"  VIX/VIX3M Ratio:            {vix_term_ratio:.3f}" if vix_term_ratio else "  VIX/VIX3M Ratio:            --")

        elif format == 'json':
            result = {
                "composite_score": float(composite_row[1]) if composite_row and composite_row[1] else None,
                "regime": composite_row[2] if composite_row else None,
                "date": str(composite_row[0]) if composite_row else None,
                "components": {
                    "vix": float(composite_row[3]) if composite_row and composite_row[3] else None,
                    "vix_term": float(composite_row[4]) if composite_row and composite_row[4] else None,
                    "realized_vol": float(composite_row[5]) if composite_row and composite_row[5] else None,
                    "turbulence": float(composite_row[6]) if composite_row and composite_row[6] else None,
                    "garch": float(composite_row[7]) if composite_row and composite_row[7] else None
                }
            }
            click.echo(json.dumps(result, indent=2))

        db.close()

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

    The backtest evaluates:
    - Regime classification accuracy
    - Regime transition timing
    - Component indicator stability
    - Model parameter drift

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

        db = get_db_manager()

        # Fetch price data from database
        import pandas as pd
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT sp.ticker, sp.date, sp.open, sp.high, sp.low, sp.close, sp.volume
                    FROM stock_prices sp
                    WHERE sp.date >= %s AND sp.date <= %s
                    ORDER BY sp.date
                """, (start_date.date(), end_date.date()))
                rows = cur.fetchall()

        if not rows:
            click.echo("Error: No price data found in database for the specified period.", err=True)
            click.echo("Run 'turbulence fetch-data' first.", err=True)
            sys.exit(1)

        columns = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']
        all_prices = pd.DataFrame(rows, columns=columns)
        all_prices['date'] = pd.to_datetime(all_prices['date'])
        # Convert Decimal types from PostgreSQL to float for numpy compatibility
        for col in ['open', 'high', 'low', 'close', 'volume']:
            all_prices[col] = pd.to_numeric(all_prices[col], errors='coerce')

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

        def progress_cb(current, total):
            pass  # Progress shown via click.progressbar below

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

        db.close()
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
    - Correlation matrices and PCA analysis
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

        db = get_db_manager()

        from turbulence.report import generate_report

        output_path = generate_report(
            db=db,
            start_date=start_date,
            end_date=end_date,
            output_path=output,
            format=format,
            include_charts=include_charts,
        )

        db.close()
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
        from datetime import datetime, timedelta
        import subprocess
        import os

        # Determine date range
        if last_3m:
            start = datetime.now() - timedelta(days=90)
            start_date = start.strftime('%Y-%m-%d')
            if not output:
                output = f"turbulence_3months.png"
        elif last_6m:
            start = datetime.now() - timedelta(days=180)
            start_date = start.strftime('%Y-%m-%d')
            if not output:
                output = f"turbulence_6months.png"
        elif ytd or (start_date is None and end_date is None):
            start_date = f"{datetime.now().year}-01-01"
            if not output:
                output = f"turbulence_ytd_{datetime.now().year}.png"
        else:
            if start_date:
                start_date = start_date.strftime('%Y-%m-%d')
            if end_date:
                end_date = end_date.strftime('%Y-%m-%d')

        # Build command
        script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'plot_turbulence.py')
        cmd = ['python', script_path]

        if start_date:
            cmd.extend(['--start-date', start_date])
        if end_date:
            cmd.extend(['--end-date', end_date])
        if output:
            cmd.extend(['--output', output])

        click.echo(f"Generating chart from {start_date or 'earliest'} to {end_date or 'today'}...")

        # Run the plot script
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            click.echo(result.stdout)
        else:
            click.echo(f"Error generating chart: {result.stderr}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@main.command()
def init_db():
    """
    Initialize the database schema.

    Creates all required tables for storing price data, volatility metrics,
    regime classifications, and composite scores. Safe to run multiple times
    (uses CREATE TABLE IF NOT EXISTS).

    Examples:

        # Initialize database
        turbulence init-db
    """
    try:
        click.echo("Initializing database schema...")

        db = get_db_manager()
        db.create_schema()

        click.echo("✓ Database schema created successfully.")
        click.echo("\nCreated turbulence-specific tables:")
        click.echo("  - turbulence_volatility_metrics")
        click.echo("  - turbulence_regime_classifications")
        click.echo("  - turbulence_composite_scores")
        click.echo("\nNote: Uses existing stock_prices table for price data.")

        db.close()

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
