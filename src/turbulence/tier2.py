"""
Tier 2: Statistical Models for Regime Detection

This module implements advanced statistical models for detecting market regimes:
1. Gaussian Hidden Markov Model with filtered probabilities
2. GJR-GARCH(1,1) with Student's t distribution
3. Hamilton regime-switching model with variance switching
"""

import numpy as np
import pandas as pd
from hmmlearn import hmm
from arch import arch_model
from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
from typing import Tuple, Optional
import warnings


def fit_gaussian_hmm(
    returns: pd.Series,
    high_low_range: pd.Series,
    n_states: int = 2,
    n_iter: int = 100,
    random_state: int = 42
) -> Tuple[hmm.GaussianHMM, pd.DataFrame]:
    """
    Fit a Gaussian HMM using returns and high-low range as features.

    Uses forward algorithm to get filtered probabilities (not Viterbi).
    States are sorted by covariance to label low vs high volatility regimes.

    Parameters
    ----------
    returns : pd.Series
        Return series
    high_low_range : pd.Series
        High-low range series (normalized)
    n_states : int, default 2
        Number of hidden states (2 or 3)
    n_iter : int, default 100
        Number of EM iterations
    random_state : int, default 42
        Random seed for reproducibility

    Returns
    -------
    model : GaussianHMM
        Fitted HMM model with sorted states
    probabilities : pd.DataFrame
        Filtered state probabilities (using forward algorithm)
    """
    # Prepare features: returns and range
    features = pd.DataFrame({
        'returns': returns,
        'range': high_low_range
    }).dropna()

    X = features.values

    # Fit HMM
    model = hmm.GaussianHMM(
        n_components=n_states,
        covariance_type='full',
        n_iter=n_iter,
        random_state=random_state
    )

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        model.fit(X)

    # Sort states by covariance determinant (volatility)
    # Lower covariance = low volatility state
    covs = [np.linalg.det(model.covars_[i]) for i in range(n_states)]
    state_order = np.argsort(covs)

    # Reorder parameters
    model.means_ = model.means_[state_order]
    model.covars_ = model.covars_[state_order]
    model.startprob_ = model.startprob_[state_order]
    model.transmat_ = model.transmat_[state_order][:, state_order]

    # Get filtered probabilities using forward algorithm
    # This gives P(state_t | observations up to t), not Viterbi path
    log_prob, posteriors = model.score_samples(X)

    # Create DataFrame with state probabilities
    prob_df = pd.DataFrame(
        posteriors,
        index=features.index,
        columns=[f'state_{i}_prob' for i in range(n_states)]
    )

    return model, prob_df


def fit_gjr_garch(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
    dist: str = 't'
) -> Tuple:
    """
    Fit GJR-GARCH(1,1) model with Student's t distribution.

    GJR-GARCH captures asymmetric volatility response (leverage effect).

    Parameters
    ----------
    returns : pd.Series
        Return series (in percentage or decimal)
    p : int, default 1
        GARCH lag order
    q : int, default 1
        ARCH lag order
    dist : str, default 't'
        Distribution ('t' for Student's t, 'normal' for Gaussian)

    Returns
    -------
    model : ARCHModelResult
        Fitted GARCH model
    conditional_vol : pd.Series
        Conditional volatility estimates
    """
    # Remove NaN values
    returns_clean = returns.dropna()

    # Fit GJR-GARCH model
    # o=1 enables the GJR (asymmetric) component
    model = arch_model(
        returns_clean * 100,  # Scale to percentage for numerical stability
        vol='GARCH',
        p=p,
        o=1,  # GJR component
        q=q,
        dist=dist
    )

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        result = model.fit(disp='off', show_warning=False)

    # Extract conditional volatility
    conditional_vol = result.conditional_volatility / 100  # Scale back

    return result, conditional_vol


def fit_hamilton_regime_switching(
    returns: pd.Series,
    k_regimes: int = 2
) -> Tuple:
    """
    Fit Hamilton regime-switching model with variance switching.

    This model allows mean and variance to switch between regimes.

    Parameters
    ----------
    returns : pd.Series
        Return series
    k_regimes : int, default 2
        Number of regimes

    Returns
    -------
    model : MarkovRegressionResults
        Fitted regime-switching model
    regime_probs : pd.DataFrame
        Filtered and smoothed regime probabilities
    """
    # Remove NaN values
    returns_clean = returns.dropna()

    # Fit regime-switching model
    # switching_variance=True allows variance to switch between regimes
    model = MarkovRegression(
        endog=returns_clean,
        k_regimes=k_regimes,
        switching_variance=True
    )

    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        result = model.fit(disp=False)

    # Get regime probabilities
    # filtered_marginal_probabilities: P(S_t | data up to t)
    # smoothed_marginal_probabilities: P(S_t | all data)
    regime_probs = pd.DataFrame({
        **{f'regime_{i}_filtered': result.filtered_marginal_probabilities[i]
           for i in range(k_regimes)},
        **{f'regime_{i}_smoothed': result.smoothed_marginal_probabilities[i]
           for i in range(k_regimes)}
    }, index=returns_clean.index)

    return result, regime_probs


def rolling_hmm_probabilities(
    returns: pd.Series,
    high_low_range: pd.Series,
    window: int = 252,
    n_states: int = 2,
    min_periods: Optional[int] = None
) -> pd.DataFrame:
    """
    Compute rolling HMM state probabilities.

    Parameters
    ----------
    returns : pd.Series
        Return series
    high_low_range : pd.Series
        High-low range series
    window : int, default 252
        Rolling window size (e.g., 252 trading days = 1 year)
    n_states : int, default 2
        Number of HMM states
    min_periods : int, optional
        Minimum observations required. Defaults to window.

    Returns
    -------
    pd.DataFrame
        Rolling state probabilities
    """
    if min_periods is None:
        min_periods = window

    # Align series
    data = pd.DataFrame({
        'returns': returns,
        'range': high_low_range
    }).dropna()

    # Initialize result DataFrame
    prob_columns = [f'state_{i}_prob' for i in range(n_states)]
    result = pd.DataFrame(
        index=data.index,
        columns=prob_columns,
        dtype=float
    )

    # Rolling window computation
    for i in range(min_periods - 1, len(data)):
        window_start = max(0, i - window + 1)
        window_data = data.iloc[window_start:i + 1]

        if len(window_data) >= min_periods:
            try:
                _, probs = fit_gaussian_hmm(
                    window_data['returns'],
                    window_data['range'],
                    n_states=n_states
                )
                # Take the last row (current probability estimate)
                result.iloc[i] = probs.iloc[-1].values
            except Exception:
                # If fitting fails, leave as NaN
                pass

    return result


def rolling_garch_volatility(
    returns: pd.Series,
    window: int = 252,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    Compute rolling GARCH conditional volatility.

    Parameters
    ----------
    returns : pd.Series
        Return series
    window : int, default 252
        Rolling window size
    min_periods : int, optional
        Minimum observations required. Defaults to window.

    Returns
    -------
    pd.Series
        Rolling conditional volatility estimates
    """
    if min_periods is None:
        min_periods = window

    returns_clean = returns.dropna()
    result = pd.Series(index=returns_clean.index, dtype=float)

    # Rolling window computation
    for i in range(min_periods - 1, len(returns_clean)):
        window_start = max(0, i - window + 1)
        window_data = returns_clean.iloc[window_start:i + 1]

        if len(window_data) >= min_periods:
            try:
                _, cond_vol = fit_gjr_garch(window_data)
                # Take the last value (current volatility estimate)
                result.iloc[i] = cond_vol.iloc[-1]
            except Exception:
                # If fitting fails, leave as NaN
                pass

    return result


def rolling_regime_probabilities(
    returns: pd.Series,
    window: int = 252,
    k_regimes: int = 2,
    min_periods: Optional[int] = None
) -> pd.DataFrame:
    """
    Compute rolling Hamilton regime-switching probabilities.

    Parameters
    ----------
    returns : pd.Series
        Return series
    window : int, default 252
        Rolling window size
    k_regimes : int, default 2
        Number of regimes
    min_periods : int, optional
        Minimum observations required. Defaults to window.

    Returns
    -------
    pd.DataFrame
        Rolling regime probabilities (filtered)
    """
    if min_periods is None:
        min_periods = window

    returns_clean = returns.dropna()
    prob_columns = [f'regime_{i}_prob' for i in range(k_regimes)]
    result = pd.DataFrame(
        index=returns_clean.index,
        columns=prob_columns,
        dtype=float
    )

    # Rolling window computation
    for i in range(min_periods - 1, len(returns_clean)):
        window_start = max(0, i - window + 1)
        window_data = returns_clean.iloc[window_start:i + 1]

        if len(window_data) >= min_periods:
            try:
                _, probs = fit_hamilton_regime_switching(
                    window_data,
                    k_regimes=k_regimes
                )
                # Take the last filtered probability
                result.iloc[i] = [
                    probs[f'regime_{j}_filtered'].iloc[-1]
                    for j in range(k_regimes)
                ]
            except Exception:
                # If fitting fails, leave as NaN
                pass

    return result
