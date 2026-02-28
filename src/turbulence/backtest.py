"""
Walk-Forward Validation Engine for Turbulence Regime Detection

Implements proper walk-forward backtesting that slides a training window
through historical data, running the full tier1→tier2→tier3→composite
pipeline on each window and evaluating predictions on the test portion.

This avoids look-ahead bias by ensuring each prediction uses only data
available up to that point in time.
"""

import numpy as np
import pandas as pd
from typing import Optional, Callable, Dict

from turbulence.config import get_logger
from turbulence.tier1 import calculate_tier1_indicators
from turbulence.tier2 import rolling_garch_volatility
from turbulence.tier3 import calculate_tier3_indicators
from turbulence.composite import CompositeScorer

logger = get_logger(__name__)


def _run_pipeline_on_window(
    price_data: pd.DataFrame,
    returns_data: pd.DataFrame,
) -> Optional[Dict[str, pd.Series]]:
    """
    Run the full turbulence pipeline on a data window.

    Parameters
    ----------
    price_data : pd.DataFrame
        OHLCV price data with 'vix', 'vix3m', 'open', 'high', 'low', 'close' columns.
        Index is DatetimeIndex.
    returns_data : pd.DataFrame
        Multi-asset returns for Tier 3 (columns = assets, index = dates).

    Returns
    -------
    dict or None
        Pipeline results with 'composite_score' and 'regime' Series,
        plus component scores. None if pipeline fails.
    """
    try:
        # Tier 1
        tier1 = calculate_tier1_indicators(
            price_data,
            vix_col='vix',
            vix3m_col='vix3m',
        )
        vix = price_data['vix']
        vix3m = price_data.get('vix3m')
        vix_term_ratio = vix / vix3m if vix3m is not None else pd.Series(
            1.0, index=vix.index
        )

        # Tier 2 — GARCH conditional volatility
        spy_returns = price_data['close'].pct_change().dropna()
        garch_vol = rolling_garch_volatility(spy_returns, window=252, min_periods=100)

        # Tier 3 — multi-asset turbulence
        tier3 = calculate_tier3_indicators(
            returns_data,
            turbulence_window=252,
            absorption_window=min(500, len(returns_data) - 1),
            n_regimes=3,
            clustering_train_window=min(756, len(returns_data) - 50),
            clustering_refit_days=5,
        )

        # Realized volatility (Garman-Klass from Tier 1)
        realized_vol = tier1.get('garman_klass_vol', spy_returns.rolling(30).std() * np.sqrt(252))

        # Composite scoring
        scorer = CompositeScorer()
        composite_results = scorer.calculate(
            vix=vix,
            vix_term_ratio=vix_term_ratio,
            realized_vol=realized_vol,
            turbulence_index=tier3['turbulence'],
            garch_vol=garch_vol,
        )

        return composite_results

    except Exception as e:
        logger.warning(f"Pipeline failed on window: {e}")
        return None


def run_walk_forward(
    price_data: pd.DataFrame,
    returns_data: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    train_window: int = 756,
    test_window: int = 126,
    step_size: int = 63,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> pd.DataFrame:
    """
    Run walk-forward validation across historical data.

    Slides [train_start, train_end, test_start, test_end] through the data,
    running the full pipeline on each window and measuring test-period metrics.

    Parameters
    ----------
    price_data : pd.DataFrame
        Full OHLCV price data with VIX columns. Index is DatetimeIndex.
    returns_data : pd.DataFrame
        Multi-asset returns for Tier 3 indicators.
    start_date : pd.Timestamp
        Start of the backtest period.
    end_date : pd.Timestamp
        End of the backtest period.
    train_window : int, default 756
        Training window size in trading days (756 ~ 3 years).
    test_window : int, default 126
        Test window size in trading days (126 ~ 6 months).
    step_size : int, default 63
        Step size for sliding forward (63 ~ 3 months).
    progress_callback : callable, optional
        Called with (current_iteration, total_iterations) for progress updates.

    Returns
    -------
    pd.DataFrame
        Per-iteration metrics with columns:
        - iteration: iteration number
        - train_start, train_end: training period dates
        - test_start, test_end: test period dates
        - mean_composite_score: mean composite score in test window
        - std_composite_score: std of composite score in test window
        - regime_low_pct, regime_normal_pct, regime_elevated_pct, regime_extreme_pct
        - num_regime_transitions: count of regime changes in test window
        - mean_vix_component, mean_vol_component, mean_turbulence_component,
          mean_garch_component, mean_term_structure_component
    """
    # Filter data to backtest period
    mask = (price_data.index >= start_date) & (price_data.index <= end_date)
    price_subset = price_data[mask].copy()
    returns_mask = (returns_data.index >= start_date) & (returns_data.index <= end_date)
    returns_subset = returns_data[returns_mask].copy()

    total_days = len(price_subset)
    available_days = total_days - train_window
    num_iterations = max(0, (available_days - test_window) // step_size + 1)

    if num_iterations < 1:
        raise ValueError(
            f"Insufficient data for walk-forward validation. "
            f"Have {total_days} days, need at least {train_window + test_window}."
        )

    logger.info(
        f"Walk-forward: {num_iterations} iterations, "
        f"train={train_window}d, test={test_window}d, step={step_size}d"
    )

    results = []

    for iteration in range(num_iterations):
        train_start_idx = iteration * step_size
        train_end_idx = train_start_idx + train_window
        test_start_idx = train_end_idx
        test_end_idx = min(test_start_idx + test_window, total_days)

        if test_end_idx <= test_start_idx:
            break

        # Slice data for this iteration (train + test combined for pipeline)
        full_window_prices = price_subset.iloc[train_start_idx:test_end_idx]
        full_window_returns = returns_subset.iloc[train_start_idx:test_end_idx]

        # Run pipeline on full window
        pipeline_result = _run_pipeline_on_window(full_window_prices, full_window_returns)

        if pipeline_result is None:
            if progress_callback:
                progress_callback(iteration + 1, num_iterations)
            continue

        # Extract test-period results only
        test_dates = price_subset.index[test_start_idx:test_end_idx]
        composite = pipeline_result['composite_score']
        regime = pipeline_result['regime']
        components = pipeline_result.get('components', pd.DataFrame())

        # Filter to test period
        test_composite = composite.reindex(test_dates).dropna()
        test_regime = regime.reindex(test_dates).dropna()

        if len(test_composite) == 0:
            if progress_callback:
                progress_callback(iteration + 1, num_iterations)
            continue

        # Calculate regime distribution
        regime_counts = test_regime.value_counts(normalize=True)

        # Count regime transitions
        transitions = (test_regime != test_regime.shift()).sum() - 1
        transitions = max(0, transitions)

        # Component means
        test_components = components.reindex(test_dates) if not components.empty else pd.DataFrame()

        row = {
            'iteration': iteration + 1,
            'train_start': price_subset.index[train_start_idx].strftime('%Y-%m-%d'),
            'train_end': price_subset.index[train_end_idx - 1].strftime('%Y-%m-%d'),
            'test_start': test_dates[0].strftime('%Y-%m-%d'),
            'test_end': test_dates[-1].strftime('%Y-%m-%d'),
            'test_days': len(test_composite),
            'mean_composite_score': test_composite.mean(),
            'std_composite_score': test_composite.std(),
            'regime_low_pct': regime_counts.get('low', 0.0),
            'regime_normal_pct': regime_counts.get('normal', 0.0),
            'regime_elevated_pct': regime_counts.get('elevated', 0.0),
            'regime_extreme_pct': regime_counts.get('extreme', 0.0),
            'num_regime_transitions': int(transitions),
        }

        # Add component means if available
        if not test_components.empty:
            for col in test_components.columns:
                row[f'mean_{col}'] = test_components[col].mean()

        results.append(row)

        if progress_callback:
            progress_callback(iteration + 1, num_iterations)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


def summarize_backtest(results: pd.DataFrame) -> str:
    """
    Generate a human-readable summary of backtest results.

    Parameters
    ----------
    results : pd.DataFrame
        Output from run_walk_forward().

    Returns
    -------
    str
        Formatted summary text.
    """
    if results.empty:
        return "No backtest results to summarize."

    lines = []
    lines.append("Walk-Forward Backtest Summary")
    lines.append("=" * 60)
    lines.append(f"Total iterations: {len(results)}")
    lines.append(f"Period: {results['train_start'].iloc[0]} to {results['test_end'].iloc[-1]}")
    lines.append("")

    # Composite score statistics
    lines.append("Composite Score Statistics:")
    lines.append(f"  Mean:  {results['mean_composite_score'].mean():.3f}")
    lines.append(f"  Std:   {results['mean_composite_score'].std():.3f}")
    lines.append(f"  Min:   {results['mean_composite_score'].min():.3f}")
    lines.append(f"  Max:   {results['mean_composite_score'].max():.3f}")
    lines.append("")

    # Regime distribution across all iterations
    lines.append("Average Regime Distribution:")
    for regime in ['low', 'normal', 'elevated', 'extreme']:
        col = f'regime_{regime}_pct'
        if col in results.columns:
            lines.append(f"  {regime.capitalize():10s}: {results[col].mean():.1%}")
    lines.append("")

    # Transition statistics
    if 'num_regime_transitions' in results.columns:
        lines.append("Regime Transitions per Test Window:")
        lines.append(f"  Mean:  {results['num_regime_transitions'].mean():.1f}")
        lines.append(f"  Max:   {results['num_regime_transitions'].max()}")
    lines.append("")

    # Stability assessment
    score_cv = results['std_composite_score'].mean() / max(results['mean_composite_score'].mean(), 1e-6)
    lines.append("Stability Assessment:")
    if score_cv < 0.3:
        lines.append("  Composite scores are STABLE across windows (low CV)")
    elif score_cv < 0.6:
        lines.append("  Composite scores show MODERATE variation across windows")
    else:
        lines.append("  Composite scores show HIGH variation across windows")

    return "\n".join(lines)
