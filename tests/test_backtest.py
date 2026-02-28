"""Tests for the walk-forward backtest module."""

import numpy as np
import pandas as pd
import pytest

from turbulence.backtest import run_walk_forward, summarize_backtest


@pytest.fixture
def backtest_data():
    """Create synthetic data suitable for backtesting."""
    np.random.seed(42)
    dates = pd.date_range('2018-01-01', periods=1200, freq='B')
    n = len(dates)

    close = 300 + np.cumsum(np.random.randn(n) * 2)
    high = close + np.abs(np.random.randn(n)) * 3
    low = close - np.abs(np.random.randn(n)) * 3
    open_ = close + np.random.randn(n) * 1.5

    vix = 18 + np.cumsum(np.random.randn(n) * 0.3)
    vix = np.clip(vix, 10, 60)
    vix3m = 19 + np.cumsum(np.random.randn(n) * 0.2)
    vix3m = np.clip(vix3m, 11, 55)

    price_data = pd.DataFrame({
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': np.random.randint(50_000_000, 200_000_000, n),
        'vix': vix,
        'vix3m': vix3m,
    }, index=dates)

    # Multi-asset returns
    assets = {}
    for name in ['SPY', 'TLT', 'GLD', 'UUP', 'HYG']:
        p = 100 + np.cumsum(np.random.randn(n) * 1)
        assets[name] = pd.Series(p, index=dates).pct_change()
    returns_data = pd.DataFrame(assets).dropna()

    return price_data, returns_data


class TestRunWalkForward:
    def test_insufficient_data_raises(self, backtest_data):
        price_data, returns_data = backtest_data
        with pytest.raises(ValueError, match="Insufficient data"):
            run_walk_forward(
                price_data.iloc[:100],
                returns_data.iloc[:100],
                start_date=pd.Timestamp('2018-01-01'),
                end_date=pd.Timestamp('2018-06-01'),
                train_window=756,
                test_window=126,
            )

    def test_returns_dataframe(self, backtest_data):
        price_data, returns_data = backtest_data
        results = run_walk_forward(
            price_data,
            returns_data,
            start_date=pd.Timestamp('2018-01-01'),
            end_date=pd.Timestamp('2022-12-31'),
            train_window=500,
            test_window=63,
            step_size=63,
        )
        assert isinstance(results, pd.DataFrame)
        if not results.empty:
            assert 'iteration' in results.columns
            assert 'mean_composite_score' in results.columns
            assert 'num_regime_transitions' in results.columns


class TestSummarizeBacktest:
    def test_empty_results(self):
        result = summarize_backtest(pd.DataFrame())
        assert "No backtest results" in result

    def test_with_data(self):
        df = pd.DataFrame({
            'iteration': [1, 2],
            'train_start': ['2020-01-01', '2020-04-01'],
            'train_end': ['2022-01-01', '2022-04-01'],
            'test_start': ['2022-01-02', '2022-04-02'],
            'test_end': ['2022-07-01', '2022-10-01'],
            'test_days': [126, 126],
            'mean_composite_score': [0.35, 0.45],
            'std_composite_score': [0.10, 0.12],
            'regime_low_pct': [0.3, 0.2],
            'regime_normal_pct': [0.5, 0.4],
            'regime_elevated_pct': [0.15, 0.3],
            'regime_extreme_pct': [0.05, 0.1],
            'num_regime_transitions': [3, 5],
        })
        result = summarize_backtest(df)
        assert "Walk-Forward Backtest Summary" in result
        assert "Total iterations: 2" in result
