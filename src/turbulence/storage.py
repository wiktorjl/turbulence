"""File-based storage layer using parquet files.

Replaces PostgreSQL with local parquet files stored in ~/.turbulence/data/
(configurable via TURBULENCE_DATA_DIR env var).

File layout:
    ~/.turbulence/data/
    ├── prices/
    │   ├── SPY.parquet
    │   ├── TLT.parquet
    │   └── ...
    ├── composite_scores.parquet
    ├── regime_classifications.parquet
    └── volatility_metrics.parquet
"""

import os
from pathlib import Path

import pandas as pd

from turbulence.config import get_logger

logger = get_logger(__name__)


def get_data_dir() -> Path:
    """Return the data directory path, respecting TURBULENCE_DATA_DIR env var."""
    data_dir = os.getenv('TURBULENCE_DATA_DIR')
    if data_dir:
        return Path(data_dir)
    return Path.home() / '.turbulence' / 'data'


def init_data_dir() -> None:
    """Create the data directory structure."""
    data_dir = get_data_dir()
    (data_dir / 'prices').mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory initialized at {data_dir}")


def _clean_ticker_filename(ticker: str) -> str:
    """Convert ticker symbol to safe filename (e.g. ^VIX -> VIX)."""
    return ticker.replace('^', '').replace('/', '_')


def save_prices(ticker: str, df: pd.DataFrame) -> None:
    """Save price data for a ticker, merging with any existing data.

    Parameters
    ----------
    ticker : str
        Ticker symbol.
    df : pd.DataFrame
        DataFrame with columns: ticker, date, open, high, low, close, volume.
    """
    if df.empty:
        return

    data_dir = get_data_dir()
    prices_dir = data_dir / 'prices'
    prices_dir.mkdir(parents=True, exist_ok=True)

    fname = _clean_ticker_filename(ticker)
    path = prices_dir / f'{fname}.parquet'

    # Ensure date is a proper column (not index) and is datetime
    save_df = df.copy()
    if 'date' in save_df.columns:
        save_df['date'] = pd.to_datetime(save_df['date'])
    else:
        save_df = save_df.reset_index()
        save_df.rename(columns={'index': 'date'}, inplace=True)
        save_df['date'] = pd.to_datetime(save_df['date'])

    # Keep only relevant columns
    cols = [c for c in ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume'] if c in save_df.columns]
    save_df = save_df[cols]

    # Merge with existing data (upsert by date)
    if path.exists():
        existing = pd.read_parquet(path)
        existing['date'] = pd.to_datetime(existing['date'])
        combined = pd.concat([existing, save_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=['date'], keep='last')
        combined = combined.sort_values('date').reset_index(drop=True)
    else:
        combined = save_df.sort_values('date').reset_index(drop=True)

    combined.to_parquet(path, index=False, engine='pyarrow')
    logger.info(f"Saved {len(combined)} rows for {ticker}")


def load_prices(ticker: str, start_date=None, end_date=None) -> pd.DataFrame:
    """Load price data for a single ticker.

    Returns empty DataFrame if file does not exist.
    """
    data_dir = get_data_dir()
    fname = _clean_ticker_filename(ticker)
    path = data_dir / 'prices' / f'{fname}.parquet'

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(path)
    df['date'] = pd.to_datetime(df['date'])

    if start_date is not None:
        df = df[df['date'] >= pd.to_datetime(start_date)]
    if end_date is not None:
        df = df[df['date'] <= pd.to_datetime(end_date)]

    return df.sort_values('date').reset_index(drop=True)


def load_all_prices(tickers: list, start_date=None, end_date=None) -> pd.DataFrame:
    """Load and concatenate price data for multiple tickers."""
    frames = []
    for ticker in tickers:
        df = load_prices(ticker, start_date, end_date)
        if not df.empty:
            if 'ticker' not in df.columns:
                df['ticker'] = ticker
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _save_result_parquet(filename: str, df: pd.DataFrame, dedup_col: str = 'date') -> None:
    """Save a results DataFrame, merging with existing data."""
    if df.empty:
        return

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / filename

    save_df = df.copy()
    if dedup_col in save_df.columns:
        save_df[dedup_col] = pd.to_datetime(save_df[dedup_col])

    if path.exists():
        existing = pd.read_parquet(path)
        if dedup_col in existing.columns:
            existing[dedup_col] = pd.to_datetime(existing[dedup_col])
        combined = pd.concat([existing, save_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=[dedup_col], keep='last')
        combined = combined.sort_values(dedup_col).reset_index(drop=True)
    else:
        combined = save_df.sort_values(dedup_col).reset_index(drop=True)

    combined.to_parquet(path, index=False, engine='pyarrow')


def _load_result_parquet(filename: str, start_date=None, end_date=None) -> pd.DataFrame:
    """Load a results parquet file with optional date filtering."""
    data_dir = get_data_dir()
    path = data_dir / filename

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_parquet(path)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        if start_date is not None:
            df = df[df['date'] >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df['date'] <= pd.to_datetime(end_date)]

    return df.sort_values('date').reset_index(drop=True) if 'date' in df.columns else df


def save_composite_scores(df: pd.DataFrame) -> None:
    """Save composite turbulence scores."""
    _save_result_parquet('composite_scores.parquet', df)


def load_composite_scores(start_date=None, end_date=None) -> pd.DataFrame:
    """Load composite turbulence scores."""
    return _load_result_parquet('composite_scores.parquet', start_date, end_date)


def save_regime_classifications(df: pd.DataFrame) -> None:
    """Save regime classification data."""
    _save_result_parquet('regime_classifications.parquet', df)


def load_regime_classifications(start_date=None, end_date=None) -> pd.DataFrame:
    """Load regime classification data."""
    return _load_result_parquet('regime_classifications.parquet', start_date, end_date)


def save_volatility_metrics(df: pd.DataFrame) -> None:
    """Save volatility metric data."""
    _save_result_parquet('volatility_metrics.parquet', df, dedup_col='date')


def load_volatility_metrics(start_date=None, end_date=None) -> pd.DataFrame:
    """Load volatility metric data."""
    return _load_result_parquet('volatility_metrics.parquet', start_date, end_date)
