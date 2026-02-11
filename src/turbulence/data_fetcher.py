"""Data fetching module for market data from Polygon.io and yfinance."""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf
from psycopg2.extensions import connection


class DataFetcher:
    """Fetches market data from Polygon.io with yfinance fallback."""

    # Default tickers for turbulence analysis
    DEFAULT_TICKERS = ['SPY', 'TLT', 'GLD', 'UUP', 'HYG', '^VIX', '^VIX3M']

    def __init__(self, polygon_api_key: Optional[str] = None):
        """
        Initialize data fetcher.

        Args:
            polygon_api_key: Polygon.io API key. If None, reads from POLYGON_API_KEY env var.
        """
        self.polygon_api_key = polygon_api_key or os.getenv('POLYGON_API_KEY')
        self.polygon_base_url = "https://api.polygon.io/v2"

    def _fetch_from_polygon(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data from Polygon.io API.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        if not self.polygon_api_key:
            return None

        # Clean ticker (remove ^ prefix for VIX tickers)
        polygon_ticker = ticker.replace('^', '')

        # Map common tickers to Polygon format
        ticker_map = {
            'VIX': 'VX',
            'VIX3M': 'VIX3M',
            'UUP': 'UUP',
            'SPY': 'SPY',
            'TLT': 'TLT',
            'GLD': 'GLD',
            'HYG': 'HYG'
        }
        polygon_ticker = ticker_map.get(polygon_ticker, polygon_ticker)

        url = f"{self.polygon_base_url}/aggs/ticker/{polygon_ticker}/range/1/day/{start_date}/{end_date}"
        params = {
            'adjusted': 'true',
            'sort': 'asc',
            'apiKey': self.polygon_api_key
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != 'OK' or not data.get('results'):
                return None

            # Convert to DataFrame
            df = pd.DataFrame(data['results'])
            df['date'] = pd.to_datetime(df['t'], unit='ms').dt.date
            df = df.rename(columns={
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })
            df['ticker'] = ticker
            df = df[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
            df = df.sort_values('date').reset_index(drop=True)

            return df

        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"Polygon.io fetch failed for {ticker}: {e}")
            return None

    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data from yfinance as fallback.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            DataFrame with OHLCV data, or None if fetch fails
        """
        try:
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
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
            print(f"yfinance fetch failed for {ticker}: {e}")
            return None

    def fetch_ticker_data(
        self,
        ticker: str,
        start_date: str,
        end_date: Optional[str] = None,
        use_polygon_first: bool = True
    ) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single ticker, trying Polygon.io first then yfinance.

        Args:
            ticker: Stock ticker symbol
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format. If None, uses today.
            use_polygon_first: If True, try Polygon.io before yfinance

        Returns:
            DataFrame with OHLCV data, or None if both sources fail
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        df = None

        if use_polygon_first:
            df = self._fetch_from_polygon(ticker, start_date, end_date)
            if df is not None:
                print(f"Fetched {ticker} from Polygon.io: {len(df)} rows")
                return df

        # Fallback to yfinance
        df = self._fetch_from_yfinance(ticker, start_date, end_date)
        if df is not None:
            print(f"Fetched {ticker} from yfinance: {len(df)} rows")
            return df

        print(f"Failed to fetch {ticker} from both sources")
        return None

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

    def _ensure_ticker_in_companies(self, conn: connection, ticker: str) -> None:
        """
        Ensure ticker exists in companies table (for foreign key constraint).

        Args:
            conn: PostgreSQL connection
            ticker: Stock ticker symbol
        """
        with conn.cursor() as cur:
            # Check if ticker exists in companies table
            cur.execute("SELECT COUNT(*) FROM companies WHERE ticker = %s", (ticker,))
            exists = cur.fetchone()[0] > 0

            if not exists:
                # Insert minimal record to satisfy foreign key constraint
                # Determine ticker name based on symbol
                ticker_names = {
                    'SPY': 'SPDR S&P 500 ETF Trust',
                    'TLT': 'iShares 20+ Year Treasury Bond ETF',
                    'GLD': 'SPDR Gold Trust',
                    'UUP': 'Invesco DB US Dollar Index Bullish Fund',
                    'HYG': 'iShares iBoxx $ High Yield Corporate Bond ETF',
                    '^VIX': 'CBOE Volatility Index',
                    '^VIX3M': 'CBOE 3-Month Volatility Index',
                    'VIX': 'CBOE Volatility Index',
                    'VIX3M': 'CBOE 3-Month Volatility Index',
                }
                name = ticker_names.get(ticker, f'{ticker} (Auto-added by Turbulence)')

                cur.execute("""
                    INSERT INTO companies (ticker, name, type, active)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (ticker) DO NOTHING
                """, (ticker, name, 'ETF' if ticker not in ['^VIX', '^VIX3M', 'VIX', 'VIX3M'] else 'INDEX', True))

    def store_price_data(
        self,
        conn: connection,
        df: pd.DataFrame
    ) -> Tuple[int, int]:
        """
        Store price data in existing stock_prices table.

        Handles foreign key constraint by ensuring tickers exist in companies table first.

        Args:
            conn: PostgreSQL connection
            df: DataFrame with columns: ticker, date, open, high, low, close, volume

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        if df.empty:
            return 0, 0

        # Ensure all tickers exist in companies table (for foreign key constraint)
        unique_tickers = df['ticker'].unique()
        for ticker in unique_tickers:
            self._ensure_ticker_in_companies(conn, ticker)

        inserted = 0
        updated = 0

        with conn.cursor() as cur:
            for _, row in df.iterrows():
                # Check if record exists
                cur.execute("""
                    SELECT COUNT(*) FROM stock_prices
                    WHERE ticker = %s AND date = %s
                """, (row['ticker'], row['date']))

                exists = cur.fetchone()[0] > 0

                if exists:
                    cur.execute("""
                        UPDATE stock_prices
                        SET open = %s, high = %s, low = %s, close = %s, volume = %s
                        WHERE ticker = %s AND date = %s
                    """, (
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume']) if pd.notna(row['volume']) else None,
                        row['ticker'],
                        row['date']
                    ))
                    updated += 1
                else:
                    cur.execute("""
                        INSERT INTO stock_prices (ticker, date, open, high, low, close, volume)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['ticker'],
                        row['date'],
                        float(row['open']),
                        float(row['high']),
                        float(row['low']),
                        float(row['close']),
                        int(row['volume']) if pd.notna(row['volume']) else None
                    ))
                    inserted += 1

        return inserted, updated

    def fetch_and_store(
        self,
        conn: connection,
        tickers: Optional[List[str]] = None,
        start_date: str = '2010-01-01',
        end_date: Optional[str] = None
    ) -> dict:
        """
        Fetch data for multiple tickers and store in database.

        Args:
            conn: PostgreSQL connection
            tickers: List of ticker symbols. If None, uses DEFAULT_TICKERS
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format. If None, uses today.

        Returns:
            Dictionary with statistics about the operation
        """
        df = self.fetch_multiple_tickers(tickers, start_date, end_date)
        if df.empty:
            return {'status': 'error', 'message': 'No data fetched'}

        inserted, updated = self.store_price_data(conn, df)

        return {
            'status': 'success',
            'tickers': df['ticker'].nunique(),
            'total_rows': len(df),
            'inserted': inserted,
            'updated': updated,
            'date_range': f"{df['date'].min()} to {df['date'].max()}"
        }


def get_data_fetcher() -> DataFetcher:
    """
    Factory function to create DataFetcher instance.

    Returns:
        Configured DataFetcher instance
    """
    return DataFetcher()
