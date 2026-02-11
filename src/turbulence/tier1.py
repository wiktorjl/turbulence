"""
Tier 1 Turbulence Indicators.

This module implements basic volatility and market regime indicators:
- VIX regime classification
- VIX term structure analysis
- Garman-Klass volatility estimation
- Percentile-based regime classification
"""

import numpy as np
import pandas as pd
from typing import Optional


def classify_vix_regime(vix_series: pd.Series) -> pd.Series:
    """
    Classify VIX values into market regimes.

    Regime thresholds:
    - <15: complacent
    - 15-20: normal
    - 20-25: elevated
    - 25-30: high
    - >30: panic

    Parameters
    ----------
    vix_series : pd.Series
        VIX index values

    Returns
    -------
    pd.Series
        Regime classification labels
    """
    def _classify_value(vix: float) -> str:
        if pd.isna(vix):
            return np.nan
        elif vix < 15:
            return 'complacent'
        elif vix < 20:
            return 'normal'
        elif vix < 25:
            return 'elevated'
        elif vix < 30:
            return 'high'
        else:
            return 'panic'

    return vix_series.apply(_classify_value)


def calculate_vix_term_structure(vix: pd.Series, vix3m: pd.Series) -> pd.Series:
    """
    Calculate VIX term structure ratio (VIX/VIX3M).

    A ratio >1.0 indicates backwardation, suggesting market stress.
    A ratio <1.0 indicates contango, suggesting normal market conditions.

    Parameters
    ----------
    vix : pd.Series
        VIX (30-day implied volatility) values
    vix3m : pd.Series
        VIX3M (3-month implied volatility) values

    Returns
    -------
    pd.Series
        VIX/VIX3M ratio
    """
    return vix / vix3m


def classify_vix_term_structure(vix: pd.Series, vix3m: pd.Series) -> pd.Series:
    """
    Classify VIX term structure into stress regimes.

    Parameters
    ----------
    vix : pd.Series
        VIX (30-day implied volatility) values
    vix3m : pd.Series
        VIX3M (3-month implied volatility) values

    Returns
    -------
    pd.Series
        Regime classification: 'stress' (>1.0) or 'normal' (<=1.0)
    """
    ratio = calculate_vix_term_structure(vix, vix3m)
    return ratio.apply(lambda x: 'stress' if x > 1.0 else 'normal' if pd.notna(x) else np.nan)


def calculate_garman_klass_volatility(
    df: pd.DataFrame,
    high_col: str = 'high',
    low_col: str = 'low',
    close_col: str = 'close',
    open_col: str = 'open',
    window: int = 30,
    annualize: bool = True
) -> pd.Series:
    """
    Calculate Garman-Klass volatility estimator.

    Formula:
    σ²_GK = 0.5 × ln(H/L)² − (2·ln2 − 1) × ln(C/O)²

    This estimator is more efficient than close-to-close volatility as it
    incorporates intraday high-low range information.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing OHLC price data
    high_col : str, default 'high'
        Column name for high prices
    low_col : str, default 'low'
        Column name for low prices
    close_col : str, default 'close'
        Column name for close prices
    open_col : str, default 'open'
        Column name for open prices
    window : int, default 30
        Rolling window size in days
    annualize : bool, default True
        Whether to annualize the volatility (multiply by sqrt(252))

    Returns
    -------
    pd.Series
        Garman-Klass volatility estimates
    """
    # Calculate log ratios
    log_hl = np.log(df[high_col] / df[low_col])
    log_co = np.log(df[close_col] / df[open_col])

    # Garman-Klass variance estimator
    # σ²_GK = 0.5 × ln(H/L)² − (2·ln2 − 1) × ln(C/O)²
    variance_gk = 0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2

    # Calculate rolling mean of variance
    rolling_variance = variance_gk.rolling(window=window).mean()

    # Convert to volatility (standard deviation)
    volatility = np.sqrt(rolling_variance)

    # Annualize if requested
    if annualize:
        volatility = volatility * np.sqrt(252)

    return volatility


def classify_by_percentile(
    series: pd.Series,
    window: int = 252,
    thresholds: Optional[dict] = None
) -> pd.Series:
    """
    Classify values based on rolling percentile ranks.

    Default thresholds:
    - <10th percentile: very_low
    - 10-25th percentile: low
    - 25-75th percentile: normal
    - 75-90th percentile: high
    - >90th percentile: very_high

    Parameters
    ----------
    series : pd.Series
        Input data series
    window : int, default 252
        Rolling window size (252 trading days = 1 year)
    thresholds : dict, optional
        Custom percentile thresholds. Format:
        {10: 'very_low', 25: 'low', 75: 'normal', 90: 'high', 100: 'very_high'}

    Returns
    -------
    pd.Series
        Regime classification labels
    """
    if thresholds is None:
        thresholds = {
            10: 'very_low',
            25: 'low',
            75: 'normal',
            90: 'high',
            100: 'very_high'
        }

    def _percentile_rank(window_data):
        """Calculate percentile rank for the last value in window."""
        if len(window_data) < 2:
            return np.nan
        current_value = window_data.iloc[-1]
        percentile = (window_data < current_value).sum() / len(window_data) * 100
        return percentile

    # Calculate rolling percentile ranks
    percentile_ranks = series.rolling(window=window).apply(_percentile_rank, raw=False)

    # Classify based on thresholds
    def _classify_percentile(pct: float) -> str:
        if pd.isna(pct):
            return np.nan

        sorted_thresholds = sorted(thresholds.items())
        for threshold, label in sorted_thresholds:
            if pct < threshold:
                return label
        return sorted_thresholds[-1][1]

    return percentile_ranks.apply(_classify_percentile)


def calculate_tier1_indicators(
    df: pd.DataFrame,
    vix_col: str = 'vix',
    vix3m_col: Optional[str] = None,
    high_col: str = 'high',
    low_col: str = 'low',
    close_col: str = 'close',
    open_col: str = 'open'
) -> pd.DataFrame:
    """
    Calculate all Tier 1 indicators for a given dataset.

    Parameters
    ----------
    df : pd.DataFrame
        Input DataFrame with market data
    vix_col : str, default 'vix'
        Column name for VIX values
    vix3m_col : str, optional
        Column name for VIX3M values (if available)
    high_col : str, default 'high'
        Column name for high prices
    low_col : str, default 'low'
        Column name for low prices
    close_col : str, default 'close'
        Column name for close prices
    open_col : str, default 'open'
        Column name for open prices

    Returns
    -------
    pd.DataFrame
        DataFrame with all Tier 1 indicator columns added
    """
    result = df.copy()

    # VIX regime classification
    if vix_col in df.columns:
        result['vix_regime'] = classify_vix_regime(df[vix_col])

        # VIX percentile classification
        result['vix_percentile_regime'] = classify_by_percentile(
            df[vix_col],
            window=252
        )

    # VIX term structure
    if vix3m_col and vix3m_col in df.columns:
        result['vix_term_structure_ratio'] = calculate_vix_term_structure(
            df[vix_col],
            df[vix3m_col]
        )
        result['vix_term_structure_regime'] = classify_vix_term_structure(
            df[vix_col],
            df[vix3m_col]
        )

    # Garman-Klass volatility (if OHLC data available)
    required_cols = {high_col, low_col, close_col, open_col}
    if required_cols.issubset(df.columns):
        result['garman_klass_vol'] = calculate_garman_klass_volatility(
            df,
            high_col=high_col,
            low_col=low_col,
            close_col=close_col,
            open_col=open_col,
            window=30,
            annualize=True
        )

        # GK volatility percentile classification
        result['gk_vol_percentile_regime'] = classify_by_percentile(
            result['garman_klass_vol'],
            window=252
        )

    return result
