"""
CLI commands for market regime status monitoring and backtesting.

Provides the `status` and `backtest` subcommands for the turbulence CLI.
"""

import sys
from datetime import datetime

import click

from turbulence import storage


def _format_component_value(value, fmt=".3f"):
    """Format a numeric value for display, returning '--' if NaN/None."""
    import pandas as pd
    if value is not None and pd.notna(value):
        return f"{value:{fmt}}"
    return "--"


def _format_status_table(composite_row, regime_row, detailed):
    """
    Print regime status in human-readable table format.

    Parameters
    ----------
    composite_row : pd.Series or None
        Latest composite score record.
    regime_row : pd.Series or None
        Latest regime classification record.
    detailed : bool
        Whether to show component-level detail.
    """
    import pandas as pd

    if composite_row is not None:
        comp_score = composite_row.get('composite_score')
        regime_label = composite_row.get('regime_label')
        comp_date = composite_row.get('date')
        click.echo(
            f"\nComposite Turbulence Score: {comp_score:.3f}"
            if comp_score else "\nComposite Turbulence Score: --"
        )
        click.echo(
            f"Current Regime: {regime_label.upper()}"
            if regime_label else "Current Regime: --"
        )
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
            components = [
                ("VIX Component", 'vix_component'),
                ("VIX Term Structure", 'vix_term_component'),
                ("Realized Volatility", 'realized_vol_component'),
                ("Turbulence Index", 'turbulence_component'),
                ("GARCH Conditional Vol", 'garch_component'),
            ]
            for label, key in components:
                val = _format_component_value(composite_row.get(key))
                click.echo(f"  {label + ':':<30}{val}")

        if regime_row is not None:
            click.echo("\nVIX Data:")
            vix_level = _format_component_value(regime_row.get('vix_level'), ".2f")
            vix_regime = regime_row.get('vix_regime')
            vix_ratio = _format_component_value(regime_row.get('vix_term_structure_ratio'))
            click.echo(f"  {'VIX Level:':<30}{vix_level}")
            click.echo(f"  {'VIX Regime:':<30}{vix_regime if vix_regime and pd.notna(vix_regime) else '--'}")
            click.echo(f"  {'VIX/VIX3M Ratio:':<30}{vix_ratio}")


def _format_status_json(composite_row):
    """
    Print regime status as JSON.

    Parameters
    ----------
    composite_row : pd.Series or None
        Latest composite score record.
    """
    import json
    import pandas as pd

    def _safe_float(row, key):
        if row is not None and pd.notna(row.get(key)):
            return float(row[key])
        return None

    result = {
        "composite_score": _safe_float(composite_row, 'composite_score'),
        "regime": composite_row['regime_label'] if composite_row is not None else None,
        "date": str(composite_row['date']) if composite_row is not None else None,
        "components": {
            "vix": _safe_float(composite_row, 'vix_component'),
            "vix_term": _safe_float(composite_row, 'vix_term_component'),
            "realized_vol": _safe_float(composite_row, 'realized_vol_component'),
            "turbulence": _safe_float(composite_row, 'turbulence_component'),
            "garch": _safe_float(composite_row, 'garch_component'),
        }
    }
    click.echo(json.dumps(result, indent=2))


@click.command()
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

        if date is None:
            date_str = "latest available"
        else:
            date_str = date.date()

        click.echo(f"Market Regime Status as of {date_str}")
        click.echo("=" * 60)

        # Load stored results
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
            _format_status_table(composite_row, regime_row, detailed)
        elif format == 'json':
            _format_status_json(composite_row)

    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)


@click.command()
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

        total_days = (end_date - start_date).days
        available_days = total_days - train_window
        num_iterations = max(0, (available_days - test_window) // step_size + 1)

        click.echo(f"Estimated iterations: {num_iterations}")

        if num_iterations < 1:
            click.echo("Error: Insufficient data for walk-forward validation.", err=True)
            click.echo(f"Need at least {train_window + test_window} days of data.", err=True)
            sys.exit(1)

        import pandas as pd

        # Load multi-ticker price data
        tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']
        all_prices = storage.load_all_prices(tickers, start_date, end_date)

        if all_prices.empty:
            click.echo("Error: No price data found for the specified period.", err=True)
            click.echo("Run 'turbulence fetch-data' first.", err=True)
            sys.exit(1)

        all_prices['date'] = pd.to_datetime(all_prices['date'])

        # Build price_data: SPY OHLCV joined with VIX columns
        spy = all_prices[all_prices['ticker'] == 'SPY'].set_index('date').sort_index()
        vix = all_prices[all_prices['ticker'] == '^VIX'].set_index('date')['close'].rename('vix')
        vix3m = all_prices[all_prices['ticker'] == '^VIX3M'].set_index('date')['close'].rename('vix3m')

        price_data = spy[['open', 'high', 'low', 'close', 'volume']].copy()
        price_data = price_data.join(vix).join(vix3m)
        price_data = price_data.dropna(subset=['close'])

        # Build multi-asset returns for Tier 3
        asset_tickers = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG']
        returns_frames = {}
        for ticker in asset_tickers:
            t_data = all_prices[all_prices['ticker'] == ticker].set_index('date')['close']
            if not t_data.empty:
                returns_frames[ticker] = t_data.pct_change()
        returns_data = pd.DataFrame(returns_frames).dropna()

        if len(price_data) < train_window + test_window:
            click.echo(
                f"Error: Only {len(price_data)} days of data, "
                f"need at least {train_window + test_window}.",
                err=True
            )
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
