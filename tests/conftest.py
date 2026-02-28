"""Shared test fixtures for turbulence tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_dates():
    """Generate 500 trading days of dates."""
    return pd.date_range(start='2020-01-01', periods=500, freq='B')


@pytest.fixture
def synthetic_returns(sample_dates):
    """Generate synthetic multi-asset returns with regime switches."""
    np.random.seed(42)
    n_days = len(sample_dates)
    n_assets = 5

    returns = []
    for i in range(n_days):
        if i < n_days // 3:
            vol = 0.01
        elif i < 2 * n_days // 3:
            vol = 0.02
        else:
            vol = 0.04

        base = np.random.randn() * vol
        asset_returns = base + np.random.randn(n_assets) * vol * 0.5
        returns.append(asset_returns)

    return pd.DataFrame(
        returns,
        index=sample_dates,
        columns=[f'asset_{i}' for i in range(n_assets)],
    )


@pytest.fixture
def sample_ohlcv(sample_dates):
    """Generate synthetic OHLCV data for SPY-like prices."""
    np.random.seed(42)
    n = len(sample_dates)

    close = 300 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n)) * 3
    low = close - np.abs(np.random.randn(n)) * 3
    open_ = close + np.random.randn(n) * 1.5
    volume = np.random.randint(50_000_000, 200_000_000, size=n)

    return pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }, index=sample_dates)


@pytest.fixture
def sample_vix(sample_dates):
    """Generate synthetic VIX data."""
    np.random.seed(42)
    n = len(sample_dates)
    vix = 18 + np.cumsum(np.random.randn(n) * 0.5)
    vix = np.clip(vix, 10, 80)
    return pd.Series(vix, index=sample_dates, name='vix')


@pytest.fixture
def sample_vix3m(sample_dates):
    """Generate synthetic VIX3M data (typically smoother than VIX)."""
    np.random.seed(43)
    n = len(sample_dates)
    vix3m = 19 + np.cumsum(np.random.randn(n) * 0.3)
    vix3m = np.clip(vix3m, 11, 70)
    return pd.Series(vix3m, index=sample_dates, name='vix3m')


@pytest.fixture
def sample_composite_scores():
    """Generate sample composite scores for testing."""
    dates = pd.date_range('2024-01-01', periods=20, freq='B')
    scores = pd.Series([
        0.10, 0.20, 0.30, 0.40, 0.55, 0.60, 0.80, 0.90,
        0.70, 0.60, 0.45, 0.30, 0.55, 0.60, 0.65, 0.70,
        0.40, 0.35, 0.30, 0.25,
    ], index=dates)
    return scores
