"""Tests for composite scoring and regime classification."""

import numpy as np
import pandas as pd
import pytest

from turbulence.composite import (
    calculate_percentile_rank,
    normalize_vix_term_structure,
    calculate_composite_score,
    classify_regime_simple,
    apply_persistence_filter,
    CompositeScorer,
    Regime,
    DEFAULT_WEIGHTS,
)


class TestCalculatePercentileRank:
    def test_basic(self):
        np.random.seed(42)
        s = pd.Series(np.random.randn(300))
        result = calculate_percentile_rank(s, window=252)
        valid = result.dropna()
        assert (valid >= 0).all()
        assert (valid <= 1).all()


class TestNormalizeVixTermStructure:
    def test_boundaries(self):
        ratios = pd.Series([0.8, 0.9, 1.0, 1.1, 1.2])
        result = normalize_vix_term_structure(ratios)
        assert abs(result.iloc[0] - 0.0) < 1e-10  # 0.8 -> clamped to 0
        assert abs(result.iloc[1] - 0.0) < 1e-10  # 0.9 -> 0
        assert abs(result.iloc[2] - 0.5) < 1e-10  # 1.0 -> 0.5
        assert abs(result.iloc[3] - 1.0) < 1e-10  # 1.1 -> 1.0
        assert abs(result.iloc[4] - 1.0) < 1e-10  # 1.2 -> clamped to 1


class TestClassifyRegimeSimple:
    def test_threshold_boundaries(self):
        scores = pd.Series([0.10, 0.30, 0.55, 0.80])
        result = classify_regime_simple(scores)
        assert result.iloc[0] == 'low'
        assert result.iloc[1] == 'normal'
        assert result.iloc[2] == 'elevated'
        assert result.iloc[3] == 'extreme'

    def test_no_path_dependence(self, sample_composite_scores):
        """Same score should always produce same regime regardless of history."""
        result = classify_regime_simple(sample_composite_scores)
        # All 0.60 scores should map to 'elevated'
        mask = sample_composite_scores == 0.60
        regimes_at_060 = result[mask]
        assert len(regimes_at_060.unique()) == 1
        assert regimes_at_060.iloc[0] == 'elevated'

    def test_exact_boundaries(self):
        scores = pd.Series([0.0, 0.25, 0.50, 0.75, 1.0])
        result = classify_regime_simple(scores)
        assert result.iloc[0] == 'low'       # 0.00 < 0.25
        assert result.iloc[1] == 'normal'    # 0.25 >= 0.25
        assert result.iloc[2] == 'elevated'  # 0.50 >= 0.50
        assert result.iloc[3] == 'extreme'   # 0.75 >= 0.75
        assert result.iloc[4] == 'extreme'   # 1.00 >= 0.75

    def test_empty(self):
        result = classify_regime_simple(pd.Series(dtype=float))
        assert len(result) == 0


class TestApplyPersistenceFilter:
    def test_prevents_rapid_switching(self):
        regimes = pd.Series(['low', 'normal', 'low', 'low', 'low'])
        result = apply_persistence_filter(regimes, min_consecutive_days=3)
        # Single 'normal' blip should be filtered out
        assert result.iloc[1] == 'low'

    def test_allows_sustained_transition(self):
        regimes = pd.Series(['low', 'normal', 'normal', 'normal', 'normal'])
        result = apply_persistence_filter(regimes, min_consecutive_days=3)
        # After 3 consecutive 'normal' days, should transition
        assert result.iloc[3] == 'normal'

    def test_empty_series(self):
        result = apply_persistence_filter(pd.Series(dtype=object))
        assert len(result) == 0

    def test_comprehensive(self, sample_composite_scores):
        raw = classify_regime_simple(sample_composite_scores)
        filtered = apply_persistence_filter(raw, min_consecutive_days=3)
        # Filtered should have fewer transitions than raw
        raw_transitions = (raw != raw.shift()).sum()
        filtered_transitions = (filtered != filtered.shift()).sum()
        assert filtered_transitions <= raw_transitions


class TestCompositeScorer:
    def test_weights_validation(self):
        with pytest.raises(ValueError, match="sum to 1.0"):
            CompositeScorer(weights={'vix_percentile': 0.5})

    def test_calculate(self):
        dates = pd.date_range('2020-01-01', periods=300, freq='B')
        np.random.seed(42)
        vix = pd.Series(np.random.uniform(12, 35, 300), index=dates)
        vix_term = pd.Series(np.random.uniform(0.85, 1.15, 300), index=dates)
        rvol = pd.Series(np.random.uniform(0.05, 0.4, 300), index=dates)
        turb = pd.Series(np.random.uniform(0, 20, 300), index=dates)
        garch = pd.Series(np.random.uniform(0.005, 0.05, 300), index=dates)

        scorer = CompositeScorer()
        result = scorer.calculate(vix, vix_term, rvol, turb, garch)

        assert 'composite_score' in result
        assert 'regime' in result
        assert 'regime_raw' in result
        assert 'components' in result

        valid_scores = result['composite_score'].dropna()
        assert (valid_scores >= 0).all()
        assert (valid_scores <= 1).all()
