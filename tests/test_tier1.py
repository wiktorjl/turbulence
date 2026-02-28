"""Tests for Tier 1 indicators."""

import numpy as np
import pandas as pd
import pytest

from turbulence.tier1 import (
    classify_vix_regime,
    calculate_vix_term_structure,
    classify_vix_term_structure,
    calculate_garman_klass_volatility,
    classify_by_percentile,
    calculate_tier1_indicators,
)


class TestClassifyVixRegime:
    def test_complacent(self):
        result = classify_vix_regime(pd.Series([10.0, 12.0, 14.9]))
        assert list(result) == ['complacent', 'complacent', 'complacent']

    def test_normal(self):
        result = classify_vix_regime(pd.Series([15.0, 17.5, 19.9]))
        assert list(result) == ['normal', 'normal', 'normal']

    def test_elevated(self):
        result = classify_vix_regime(pd.Series([20.0, 22.5]))
        assert list(result) == ['elevated', 'elevated']

    def test_high(self):
        result = classify_vix_regime(pd.Series([25.0, 28.0]))
        assert list(result) == ['high', 'high']

    def test_panic(self):
        result = classify_vix_regime(pd.Series([30.0, 50.0, 80.0]))
        assert list(result) == ['panic', 'panic', 'panic']

    def test_nan_handling(self):
        result = classify_vix_regime(pd.Series([np.nan, 15.0]))
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == 'normal'


class TestVixTermStructure:
    def test_ratio_calculation(self):
        vix = pd.Series([20.0, 25.0])
        vix3m = pd.Series([22.0, 20.0])
        ratio = calculate_vix_term_structure(vix, vix3m)
        assert abs(ratio.iloc[0] - 20.0/22.0) < 1e-10
        assert abs(ratio.iloc[1] - 25.0/20.0) < 1e-10

    def test_classification(self):
        vix = pd.Series([18.0, 25.0])
        vix3m = pd.Series([22.0, 20.0])
        result = classify_vix_term_structure(vix, vix3m)
        assert result.iloc[0] == 'normal'   # 18/22 < 1.0
        assert result.iloc[1] == 'stress'   # 25/20 > 1.0


class TestGarmanKlassVolatility:
    def test_basic_calculation(self, sample_ohlcv):
        vol = calculate_garman_klass_volatility(sample_ohlcv, window=30)
        # First 29 values should be NaN (window=30)
        assert vol.iloc[:29].isna().all()
        # After warmup, values should be positive
        valid = vol.dropna()
        assert (valid > 0).all()

    def test_annualization(self, sample_ohlcv):
        vol_ann = calculate_garman_klass_volatility(sample_ohlcv, window=30, annualize=True)
        vol_raw = calculate_garman_klass_volatility(sample_ohlcv, window=30, annualize=False)
        valid_ann = vol_ann.dropna()
        valid_raw = vol_raw.dropna()
        # Annualized should be ~sqrt(252) times larger
        ratio = (valid_ann / valid_raw).mean()
        assert abs(ratio - np.sqrt(252)) < 1.0


class TestClassifyByPercentile:
    def test_basic(self):
        np.random.seed(42)
        series = pd.Series(np.random.randn(300))
        result = classify_by_percentile(series, window=252)
        # After warmup, should have classifications
        valid = result.dropna()
        assert len(valid) > 0
        assert set(valid.unique()).issubset({'very_low', 'low', 'normal', 'high', 'very_high'})


class TestCalculateTier1Indicators:
    def test_adds_columns(self, sample_ohlcv, sample_vix, sample_vix3m):
        df = sample_ohlcv.copy()
        df['vix'] = sample_vix
        df['vix3m'] = sample_vix3m

        result = calculate_tier1_indicators(df, vix_col='vix', vix3m_col='vix3m')

        assert 'vix_regime' in result.columns
        assert 'vix_term_structure_ratio' in result.columns
        assert 'garman_klass_vol' in result.columns
