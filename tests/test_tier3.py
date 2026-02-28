"""Tests for Tier 3 multi-asset turbulence indicators."""

import numpy as np
import pandas as pd
import pytest

from turbulence.tier3 import (
    KritzmanLiTurbulence,
    AbsorptionRatio,
    RegimeClustering,
    calculate_tier3_indicators,
)


class TestKritzmanLiTurbulence:
    def test_basic_calculation(self, synthetic_returns):
        kl = KritzmanLiTurbulence(window=100, min_periods=50)
        result = kl.calculate(synthetic_returns)
        assert len(result) == len(synthetic_returns)
        # First min_periods-1 should be NaN
        assert result.iloc[:49].isna().all()
        # Valid values should be non-negative
        valid = result.dropna()
        assert (valid >= 0).all()

    def test_high_vol_regime_higher(self, synthetic_returns):
        """Turbulence should be higher in the high-vol regime."""
        kl = KritzmanLiTurbulence(window=100, min_periods=50)
        result = kl.calculate(synthetic_returns)
        n = len(synthetic_returns)
        # Low vol is first third, high vol is last third
        low_turb = result.iloc[100:n//3].dropna().mean()
        high_turb = result.iloc[2*n//3:].dropna().mean()
        assert high_turb > low_turb


class TestAbsorptionRatio:
    def test_basic_calculation(self, synthetic_returns):
        ar = AbsorptionRatio(window=200, min_periods=100)
        result = ar.calculate(synthetic_returns)
        assert len(result) == len(synthetic_returns)
        valid = result.dropna()
        # Absorption ratio should be between 0 and 1
        assert (valid >= 0).all()
        assert (valid <= 1).all()


class TestRegimeClustering:
    def test_fit_predict(self, synthetic_returns):
        rc = RegimeClustering(n_regimes=3)
        rc.fit(synthetic_returns)
        regimes, probs = rc.predict(synthetic_returns)
        assert len(regimes) == len(synthetic_returns)
        assert probs.shape[1] == 3

    def test_regime_characteristics(self, synthetic_returns):
        rc = RegimeClustering(n_regimes=3)
        rc.fit(synthetic_returns)
        chars = rc.get_regime_characteristics(synthetic_returns)
        assert len(chars) == 3
        assert 'mean_volatility' in chars.columns


class TestCalculateTier3Indicators:
    def test_returns_all_keys(self, synthetic_returns):
        results = calculate_tier3_indicators(
            synthetic_returns,
            turbulence_window=50,
            absorption_window=100,
            n_regimes=3,
            clustering_train_window=120,
            clustering_refit_days=10,
        )
        assert 'turbulence' in results
        assert 'absorption_ratio' in results
        assert 'regime' in results
        assert 'regime_probs' in results

    def test_no_lookahead_bias(self):
        """Historical predictions should be stable when new data is added."""
        np.random.seed(42)
        dates = pd.date_range('2020-01-01', periods=400, freq='B')
        n_assets = 5
        data = []
        for i in range(400):
            vol = 0.01 if i < 133 else (0.02 if i < 266 else 0.04)
            base = np.random.randn() * vol
            data.append(base + np.random.randn(n_assets) * vol * 0.5)
        full = pd.DataFrame(data, index=dates, columns=[f'a{i}' for i in range(n_assets)])

        old = full.iloc[:350]
        new = full

        old_r = calculate_tier3_indicators(old, 100, 200, 3, 120, 5)
        new_r = calculate_tier3_indicators(new, 100, 200, 3, 120, 5)

        # Turbulence index uses rolling windows — should be identical on overlap
        old_t = old_r['turbulence'].iloc[320:350].dropna()
        new_t = new_r['turbulence'].iloc[320:350].dropna()
        common_t = old_t.index.intersection(new_t.index)
        assert len(common_t) > 0, "No overlapping non-NaN turbulence values"
        diff = np.abs(old_t[common_t] - new_t[common_t]).max()
        assert diff < 1e-10, f"Turbulence changed by {diff}"

        # Absorption ratio too
        old_a = old_r['absorption_ratio'].iloc[320:350].dropna()
        new_a = new_r['absorption_ratio'].iloc[320:350].dropna()
        common_a = old_a.index.intersection(new_a.index)
        assert len(common_a) > 0, "No overlapping non-NaN absorption ratio values"
        diff_a = np.abs(old_a[common_a] - new_a[common_a]).max()
        assert diff_a < 1e-10, f"Absorption ratio changed by {diff_a}"
