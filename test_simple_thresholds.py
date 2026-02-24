#!/usr/bin/env python3
"""
Test to verify simple threshold classification works correctly.
"""

import numpy as np
import pandas as pd
from turbulence.composite import classify_regime_simple, apply_persistence_filter


def test_simple_thresholds():
    """Test that simple thresholds work as expected."""

    # Create test scores that cross thresholds
    dates = pd.date_range('2024-01-01', periods=20, freq='D')
    scores = pd.Series([
        0.10,  # LOW
        0.20,  # LOW
        0.30,  # NORMAL
        0.40,  # NORMAL
        0.55,  # ELEVATED
        0.60,  # ELEVATED
        0.80,  # EXTREME
        0.90,  # EXTREME
        0.70,  # ELEVATED (dropped from EXTREME)
        0.60,  # ELEVATED
        0.45,  # NORMAL (dropped from ELEVATED)
        0.30,  # NORMAL
        0.55,  # ELEVATED (back up)
        0.60,  # ELEVATED
        0.65,  # ELEVATED
        0.70,  # ELEVATED
        0.40,  # NORMAL (dropped again)
        0.35,  # NORMAL
        0.30,  # NORMAL
        0.25,  # NORMAL (right at threshold)
    ], index=dates)

    print("Testing Simple Threshold Classification")
    print("=" * 60)
    print()

    # Test raw classification (no persistence)
    regimes_raw = classify_regime_simple(scores)

    print("RAW CLASSIFICATION (no persistence filter):")
    print("-" * 60)
    for date, score, regime in zip(dates, scores, regimes_raw):
        print(f"{date.strftime('%Y-%m-%d')}  Score: {score:.2f}  Regime: {regime}")
    print()

    # Verify key properties
    print("VERIFICATION:")
    print("-" * 60)

    # Same score always produces same regime (no path dependence)
    score_0_60_indices = scores[scores == 0.60].index
    regimes_at_060 = regimes_raw[score_0_60_indices]
    print(f"✓ Score 0.60 always produces regime: {regimes_at_060.unique()}")
    assert len(regimes_at_060.unique()) == 1, "Same score should always give same regime!"

    # Verify threshold boundaries
    assert regimes_raw[scores == 0.10].iloc[0] == 'low', "0.10 should be LOW"
    assert regimes_raw[scores == 0.30].iloc[0] == 'normal', "0.30 should be NORMAL"
    assert regimes_raw[scores == 0.55].iloc[0] == 'elevated', "0.55 should be ELEVATED"
    assert regimes_raw[scores == 0.80].iloc[0] == 'extreme', "0.80 should be EXTREME"
    print("✓ All threshold boundaries correct")
    print()

    # Test with persistence filter
    print("WITH 3-DAY PERSISTENCE FILTER:")
    print("-" * 60)
    regimes_filtered = apply_persistence_filter(regimes_raw, min_consecutive_days=3)

    for date, score, raw, filtered in zip(dates, scores, regimes_raw, regimes_filtered):
        change = " <-- FILTERED" if raw != filtered else ""
        print(f"{date.strftime('%Y-%m-%d')}  Score: {score:.2f}  "
              f"Raw: {raw:8s}  Final: {filtered:8s}{change}")
    print()

    print("PERSISTENCE FILTER EFFECTS:")
    print("-" * 60)
    different = (regimes_raw != regimes_filtered).sum()
    print(f"Dates where persistence filter changed regime: {different}")
    print(f"Total dates: {len(scores)}")
    print(f"Stability improvement: {different} regime jumps prevented")
    print()

    print("=" * 60)
    print("✓ TEST PASSED - Simple thresholds working correctly!")
    print()
    print("Key advantages:")
    print("  1. Score 0.65 always means ELEVATED, regardless of history")
    print("  2. No confusing path-dependent behavior")
    print("  3. Persistence filter prevents rapid switching")
    print("  4. Clear, reproducible regime classification")


if __name__ == '__main__':
    test_simple_thresholds()
