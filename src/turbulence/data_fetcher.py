"""Data fetching module for market data from yfinance."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd
import yfinance as yf

from turbulence import storage

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches market data from yfinance and stores to parquet."""

    # Default tickers for turbulence analysis
    DEFAULT_TICKERS = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']

    def __init__(self):
        """Initialize data fetcher."""
        pass

    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data from yfinance.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format (inclusive)

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        try:
            # yfinance uses exclusive end date, so add 1 day to include end_date
            end_date_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_date_exclusive = (end_date_dt + timedelta(days=1)).strftime('%Y-%m-%d')

            df = yf.download(
                ticker,
                start=start_date,
                end=end_date_exclusive,
                progress=False,
                auto_adjust=True
            )

            if df.empty:
                return None

            # Reset index to get date as column
            df = df.reset_index()

            # Handle MultiIndex columns (sometimes yfinance returns MultiIndex)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Standardize column names
            df.columns = [col.lower() if isinstance(col, str) else col for col in df.columns]
            if 'adj close' in df.columns:
                df = df.drop(columns=['adj close'])

            df['ticker'] = ticker
            df['date'] = pd.to_datetime(df['date']).dt.date

            # Reorder columns
            df = df[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
            df = df.sort_values('date').reset_index(drop=True)

            return df

        except Exception as e:
            logger.warning(f"yfinance fetch failed for {ticker}: {e}")
            return None

    def fetch_ticker_data(
        self,
        ticker: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single ticker via yfinance.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format. If None, uses today.

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        df = self._fetch_from_yfinance(ticker, start_date, end_date)
        if df is not None:
            logger.info(f"Fetched {ticker} from yfinance: {len(df)} rows")
            return df

        logger.warning(f"Failed to fetch {ticker}")
        return None

    def fetch_and_store(
        self,
        ticker: str,
        start_date: str,
        end_date: Optional[str] = None,
    ) -> int:
        """
        Fetch data for a single ticker and store to parquet.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format. If None, uses today.

        Returns:
            Number of rows stored.
        """
        df = self.fetch_ticker_data(ticker, start_date, end_date)
        if df is None or df.empty:
            return 0

        storage.save_prices(ticker, df)
        return len(df)

    def fetch_multiple_tickers(
        self,
        tickers: Optional[List[str]] = None,
        start_date: str = '2010-01-01',
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Fetch data for multiple tickers.

        Args:
            tickers: List of ticker symbols. If None, uses DEFAULT_TICKERS
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format. If None, uses today.

        Returns:
            Combined DataFrame with all ticker data
        """
        if tickers is None:
            tickers = self.DEFAULT_TICKERS

        all_data = []
        for ticker in tickers:
            df = self.fetch_ticker_data(ticker, start_date, end_date)
            if df is not None:
                all_data.append(df)

        if not all_data:
            return pd.DataFrame()

        return pd.concat(all_data, ignore_index=True)


def get_data_fetcher() -> DataFetcher:
    """
    Factory function to create DataFetcher instance.

    Returns:
        Configured DataFetcher instance
    """
    return DataFetcher()
