"""
Composite Scoring System for Market Regime Detection

This module combines five normalized volatility components into a composite
turbulence score with simple fixed thresholds and persistence filter.

Components:
1. VIX percentile (25%)
2. VIX term structure (15%)
3. Realized volatility percentile (20%)
4. Turbulence index percentile (25%)
5. GARCH conditional volatility percentile (15%)

Regimes (fixed thresholds):
- Low: 0.00-0.25
- Normal: 0.25-0.50
- Elevated: 0.50-0.75
- Extreme: 0.75-1.00

Whipsaw prevention: 3-day persistence filter requires regime to hold
for 3 consecutive days before confirming transition.
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple, Optional
from enum import Enum

from turbulence.config import get_logger

logger = get_logger(__name__)


class Regime(Enum):
    """Market regime classifications."""
    LOW = 'low'
    NORMAL = 'normal'
    ELEVATED = 'elevated'
    EXTREME = 'extreme'


# Default component weights
DEFAULT_WEIGHTS = {
    'vix_percentile': 0.25,
    'vix_term_structure': 0.15,
    'realized_vol_percentile': 0.20,
    'turbulence_percentile': 0.25,
    'garch_vol_percentile': 0.15
}

# Simple fixed regime thresholds (no hysteresis)
REGIME_THRESHOLDS = {
    'low_to_normal': 0.25,
    'normal_to_elevated': 0.50,
    'elevated_to_extreme': 0.75
}


def calculate_percentile_rank(
    series: pd.Series,
    window: int = 252,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Calculate rolling percentile rank (0-1) for a time series.

    Percentile rank at time t is calculated as the fraction of values
    in the rolling window that are less than the current value.

    Parameters
    ----------
    series : pd.Series
        Input time series
    window : int, default 252
        Rolling window size (252 trading days = 1 year)
    min_periods : int, optional
        Minimum observations required. Defaults to window.

    Returns
    -------
    pd.Series
        Percentile ranks normalized to [0, 1]
    """
    if min_periods is None:
        min_periods = window

    def _percentile_rank(window_data):
        """Calculate percentile rank for the last value in window."""
        if len(window_data) < 2:
            return np.nan
        current_value = window_data.iloc[-1]
        # Count values strictly less than current
        rank = (window_data < current_value).sum()
        # Normalize to [0, 1]
        percentile = rank / len(window_data)
        return percentile

    return series.rolling(window=window, min_periods=min_periods).apply(
        _percentile_rank, raw=False
    )


def normalize_vix_term_structure(vix_term_ratio: pd.Series) -> pd.Series:
    """
    Normalize VIX term structure ratio to [0, 1] scale.

    VIX/VIX3M ratio interpretation:
    - ratio < 0.9: Strong contango (low stress) -> 0.0
    - ratio = 1.0: Flat term structure (neutral) -> 0.5
    - ratio > 1.1: Strong backwardation (high stress) -> 1.0

    Parameters
    ----------
    vix_term_ratio : pd.Series
        VIX/VIX3M ratio

    Returns
    -------
    pd.Series
        Normalized term structure score [0, 1]
    """
    # Map ratio to [0, 1] using sigmoid-like transformation
    # Center at 1.0, with smooth transitions
    normalized = (vix_term_ratio - 0.9) / 0.2
    # Clamp to [0, 1]
    normalized = normalized.clip(lower=0.0, upper=1.0)
    return normalized


def calculate_composite_score(
    components: Dict[str, pd.Series],
    weights: Optional[Dict[str, float]] = None
) -> pd.Series:
    """
    Calculate weighted composite turbulence score.

    Parameters
    ----------
    components : dict
        Dictionary of normalized component series (each in [0, 1]):
        - 'vix_percentile': VIX percentile rank
        - 'vix_term_structure': Normalized VIX term structure
        - 'realized_vol_percentile': Realized volatility percentile
        - 'turbulence_percentile': Turbulence index percentile
        - 'garch_vol_percentile': GARCH volatility percentile
    weights : dict, optional
        Component weights (must sum to 1.0). Uses defaults if None.

    Returns
    -------
    pd.Series
        Composite score in [0, 1]

    Raises
    ------
    ValueError
        If weights don't sum to 1.0 or components are missing
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Validate weights
    weight_sum = sum(weights.values())
    if not np.isclose(weight_sum, 1.0, atol=1e-6):
        raise ValueError(f"Weights must sum to 1.0, got {weight_sum:.6f}")

    # Validate all components are present
    missing_components = set(weights.keys()) - set(components.keys())
    if missing_components:
        raise ValueError(f"Missing components: {missing_components}")

    # Align all series to common index
    df = pd.DataFrame(components)

    # Calculate weighted sum
    composite = pd.Series(0.0, index=df.index)
    for component, weight in weights.items():
        composite += df[component] * weight

    # Ensure bounds [0, 1]
    composite = composite.clip(lower=0.0, upper=1.0)

    return composite


def apply_persistence_filter(
    regime_series: pd.Series,
    min_consecutive_days: int = 3
) -> pd.Series:
    """
    Apply persistence filter: require N consecutive days before regime change.

    This prevents rapid regime switching due to noise.

    Parameters
    ----------
    regime_series : pd.Series
        Raw regime classifications
    min_consecutive_days : int, default 3
        Minimum consecutive days required to confirm regime change

    Returns
    -------
    pd.Series
        Filtered regime series with persistence requirement
    """
    if len(regime_series) == 0:
        return regime_series

    filtered = regime_series.copy()
    current_regime = regime_series.iloc[0]
    consecutive_count = 1

    for i in range(1, len(regime_series)):
        proposed_regime = regime_series.iloc[i]

        if pd.isna(proposed_regime):
            filtered.iloc[i] = current_regime
            consecutive_count = 0
            continue

        if proposed_regime == current_regime:
            # Same regime, reset counter
            consecutive_count = 1
        else:
            # Different regime proposed
            consecutive_count += 1

            if consecutive_count >= min_consecutive_days:
                # Confirm regime change
                current_regime = proposed_regime
                consecutive_count = 1
            else:
                # Not enough consecutive days, maintain current regime
                filtered.iloc[i] = current_regime

    return filtered


def classify_regime_simple(
    composite_score: pd.Series
) -> pd.Series:
    """
    Classify composite score into regimes using simple fixed thresholds.

    Uses clear, non-path-dependent thresholds:
    - Low: 0.00 - 0.25
    - Normal: 0.25 - 0.50
    - Elevated: 0.50 - 0.75
    - Extreme: 0.75 - 1.00

    Whipsaw prevention is handled by the persistence filter (applied separately).

    Parameters
    ----------
    composite_score : pd.Series
        Composite turbulence score [0, 1]

    Returns
    -------
    pd.Series
        Regime classifications (before persistence filter)
    """
    if len(composite_score) == 0:
        return pd.Series(dtype=object)

    regime_series = pd.Series(index=composite_score.index, dtype=object)

    # Classify each score independently using fixed thresholds
    for idx in composite_score.index:
        score = composite_score.loc[idx]

        if pd.isna(score):
            regime_series.loc[idx] = None
            continue

        # Simple threshold classification
        if score < 0.25:
            regime_series.loc[idx] = Regime.LOW.value
        elif score < 0.50:
            regime_series.loc[idx] = Regime.NORMAL.value
        elif score < 0.75:
            regime_series.loc[idx] = Regime.ELEVATED.value
        else:
            regime_series.loc[idx] = Regime.EXTREME.value

    return regime_series


class CompositeScorer:
    """
    Composite scoring system for market regime detection.

    Combines multiple normalized volatility components with configurable
    weights and persistence filtering. Uses simple fixed thresholds
    (0.25, 0.50, 0.75) with 3-day persistence filter to prevent whipsaw.
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_consecutive_days: int = 3,
        percentile_window: int = 252
    ):
        """
        Initialize composite scorer.

        Parameters
        ----------
        weights : dict, optional
            Component weights. Uses defaults if None.
        min_consecutive_days : int, default 3
            Minimum consecutive days for regime persistence filter
        percentile_window : int, default 252
            Window for percentile rank calculations (252 = 1 year)
        """
        self.weights = weights if weights is not None else DEFAULT_WEIGHTS
        self.min_consecutive_days = min_consecutive_days
        self.percentile_window = percentile_window

        # Validate weights
        weight_sum = sum(self.weights.values())
        if not np.isclose(weight_sum, 1.0, atol=1e-6):
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum:.6f}")

        logger.info(
            f"Initialized CompositeScorer with {len(self.weights)} components, "
            f"{self.min_consecutive_days}-day persistence filter"
        )

    def calculate(
        self,
        vix: pd.Series,
        vix_term_ratio: pd.Series,
        realized_vol: pd.Series,
        turbulence_index: pd.Series,
        garch_vol: pd.Series
    ) -> Dict[str, pd.Series]:
        """
        Calculate composite score and regime classification.

        Parameters
        ----------
        vix : pd.Series
            VIX index values
        vix_term_ratio : pd.Series
            VIX/VIX3M term structure ratio
        realized_vol : pd.Series
            Realized (historical) volatility
        turbulence_index : pd.Series
            Kritzman-Li turbulence index
        garch_vol : pd.Series
            GARCH conditional volatility

        Returns
        -------
        dict
            Dictionary containing:
            - 'composite_score': Composite turbulence score [0, 1]
            - 'regime': Final regime classification (with persistence)
            - 'regime_raw': Raw regime (before persistence filter)
            - 'components': DataFrame with normalized components
        """
        logger.info("Calculating composite turbulence score")

        # Step 1: Calculate percentile ranks for applicable components
        vix_pct = calculate_percentile_rank(vix, window=self.percentile_window)
        realized_vol_pct = calculate_percentile_rank(
            realized_vol, window=self.percentile_window
        )
        turbulence_pct = calculate_percentile_rank(
            turbulence_index, window=self.percentile_window
        )
        garch_vol_pct = calculate_percentile_rank(
            garch_vol, window=self.percentile_window
        )

        # Step 2: Normalize VIX term structure
        vix_term_norm = normalize_vix_term_structure(vix_term_ratio)

        # Step 3: Combine into components dictionary
        components = {
            'vix_percentile': vix_pct,
            'vix_term_structure': vix_term_norm,
            'realized_vol_percentile': realized_vol_pct,
            'turbulence_percentile': turbulence_pct,
            'garch_vol_percentile': garch_vol_pct
        }

        # Step 4: Calculate composite score
        composite_score = calculate_composite_score(components, self.weights)

        logger.info(
            f"Composite score range: [{composite_score.min():.3f}, "
            f"{composite_score.max():.3f}]"
        )

        # Step 5: Classify regimes using simple thresholds
        regime_raw = classify_regime_simple(composite_score)

        # Step 6: Apply persistence filter (prevents whipsaw)
        regime_final = apply_persistence_filter(
            regime_raw, self.min_consecutive_days
        )

        logger.info(
            f"Regime distribution: "
            f"{regime_final.value_counts().to_dict()}"
        )

        return {
            'composite_score': composite_score,
            'regime': regime_final,
            'regime_raw': regime_raw,
            'components': pd.DataFrame(components)
        }
