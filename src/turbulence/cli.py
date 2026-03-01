"""
CLI interface for the Turbulence market regime detection system.

This module provides the main Click group and lightweight commands:
init, fetch-data, and chart. Heavier commands (compute, report, status,
backtest) are defined in cli_compute.py and cli_analysis.py and registered
here via main.add_command().
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


# Register subcommands from split modules
from turbulence.cli_compute import compute, report  # noqa: E402
from turbulence.cli_analysis import status, backtest  # noqa: E402

main.add_command(compute)
main.add_command(report)
main.add_command(status)
main.add_command(backtest)


if __name__ == '__main__':
    main()
