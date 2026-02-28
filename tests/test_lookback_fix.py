"""Test that historical predictions remain stable when new data is added (no look-ahead bias)."""

import numpy as np
import pandas as pd
import pytest

from turbulence.tier3 import calculate_tier3_indicators


def generate_sample_data(n_days: int, n_assets: int = 5, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic return data for testing."""
    np.random.seed(seed)
    dates = pd.date_range(start='2020-01-01', periods=n_days, freq='B')
    returns = []
    for i in range(n_days):
        if i < n_days // 3:
            vol = 0.01
        elif i < 2 * n_days // 3:
            vol = 0.02
        else:
            vol = 0.04
        base_return = np.random.randn() * vol
        asset_returns = base_return + np.random.randn(n_assets) * vol * 0.5
        returns.append(asset_returns)
    return pd.DataFrame(returns, index=dates, columns=[f'asset_{i}' for i in range(n_assets)])


class TestHistoricalStability:
    def test_turbulence_stable(self):
        """Turbulence index should be identical on overlapping periods."""
        full_data = generate_sample_data(n_days=400, n_assets=5)
        old_data = full_data.iloc[:350]
        new_data = full_data

        old_results = calculate_tier3_indicators(
            old_data, turbulence_window=100, absorption_window=200,
            n_regimes=3, clustering_train_window=120,
        )
        new_results = calculate_tier3_indicators(
            new_data, turbulence_window=100, absorption_window=200,
            n_regimes=3, clustering_train_window=120,
        )

        old_turb = old_results['turbulence'].iloc[320:350].dropna()
        new_turb = new_results['turbulence'].iloc[320:350].dropna()
        # Compare only where both have values
        common = old_turb.index.intersection(new_turb.index)
        assert len(common) > 0, "No overlapping non-NaN values"
        assert np.abs(old_turb[common] - new_turb[common]).max() < 1e-10

    def test_absorption_ratio_stable(self):
        """Absorption ratio should be identical on overlapping periods."""
        full_data = generate_sample_data(n_days=400, n_assets=5)
        old_data = full_data.iloc[:350]
        new_data = full_data

        old_results = calculate_tier3_indicators(
            old_data, turbulence_window=100, absorption_window=200,
            n_regimes=3, clustering_train_window=120,
        )
        new_results = calculate_tier3_indicators(
            new_data, turbulence_window=100, absorption_window=200,
            n_regimes=3, clustering_train_window=120,
        )

        old_abs = old_results['absorption_ratio'].iloc[320:350].dropna()
        new_abs = new_results['absorption_ratio'].iloc[320:350].dropna()
        common = old_abs.index.intersection(new_abs.index)
        assert len(common) > 0, "No overlapping non-NaN values"
        assert np.abs(old_abs[common] - new_abs[common]).max() < 1e-10
