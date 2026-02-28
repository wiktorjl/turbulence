"""Tests for Tier 2 statistical models."""

import numpy as np
import pandas as pd
import pytest

from turbulence.tier2 import (
    fit_gjr_garch,
    rolling_garch_volatility,
)


class TestGJRGarch:
    def test_fit_basic(self):
        """Test that GARCH fits on synthetic returns."""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(500) * 0.01)
        result, cond_vol = fit_gjr_garch(returns)
        assert len(cond_vol) > 0
        assert (cond_vol.dropna() > 0).all()

    def test_conditional_vol_scale(self):
        """Test that conditional vol is in reasonable range for daily returns."""
        np.random.seed(42)
        returns = pd.Series(np.random.randn(500) * 0.01)
        _, cond_vol = fit_gjr_garch(returns)
        valid = cond_vol.dropna()
        # Daily vol should be roughly in 0.001-0.1 range
        assert valid.median() < 0.1
        assert valid.median() > 0.0001


class TestRollingGarchVolatility:
    def test_basic(self):
        """Test rolling GARCH on synthetic data with small window."""
        np.random.seed(42)
        returns = pd.Series(
            np.random.randn(300) * 0.01,
            index=pd.date_range('2020-01-01', periods=300, freq='B'),
        )
        result = rolling_garch_volatility(returns, window=100, min_periods=100)
        # First 99 should be NaN
        assert result.iloc[:99].isna().all()
        # Should have some valid values
        assert result.dropna().shape[0] > 0
