"""Test that simple threshold classification works correctly."""

import numpy as np
import pandas as pd
import pytest

from turbulence.composite import classify_regime_simple, apply_persistence_filter


class TestSimpleThresholds:
    def test_all_thresholds(self):
        """Test classification at each threshold boundary."""
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        scores = pd.Series([0.10, 0.30, 0.55, 0.80, 0.25], index=dates)
        result = classify_regime_simple(scores)
        assert result.iloc[0] == 'low'
        assert result.iloc[1] == 'normal'
        assert result.iloc[2] == 'elevated'
        assert result.iloc[3] == 'extreme'
        assert result.iloc[4] == 'normal'  # 0.25 >= 0.25 threshold

    def test_no_path_dependence(self):
        """Same score should always produce same regime."""
        dates = pd.date_range('2024-01-01', periods=20, freq='B')
        scores = pd.Series([
            0.10, 0.20, 0.30, 0.40, 0.55, 0.60, 0.80, 0.90,
            0.70, 0.60, 0.45, 0.30, 0.55, 0.60, 0.65, 0.70,
            0.40, 0.35, 0.30, 0.25,
        ], index=dates)
        result = classify_regime_simple(scores)

        # All 0.60 scores should be 'elevated'
        mask = scores == 0.60
        assert len(result[mask].unique()) == 1
        assert result[mask].iloc[0] == 'elevated'

    def test_persistence_filter_reduces_transitions(self):
        """Persistence filter should reduce or equal number of transitions."""
        dates = pd.date_range('2024-01-01', periods=20, freq='B')
        scores = pd.Series([
            0.10, 0.20, 0.30, 0.40, 0.55, 0.60, 0.80, 0.90,
            0.70, 0.60, 0.45, 0.30, 0.55, 0.60, 0.65, 0.70,
            0.40, 0.35, 0.30, 0.25,
        ], index=dates)
        raw = classify_regime_simple(scores)
        filtered = apply_persistence_filter(raw, min_consecutive_days=3)

        raw_transitions = (raw != raw.shift()).sum()
        filtered_transitions = (filtered != filtered.shift()).sum()
        assert filtered_transitions <= raw_transitions
