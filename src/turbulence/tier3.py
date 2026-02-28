"""
Tier 3: Multi-Asset Turbulence Indicators

This module implements advanced multi-asset turbulence measures:
1. Kritzman & Li Turbulence Index (Mahalanobis distance)
2. Absorption Ratio (PCA-based systemic risk measure)
3. Gaussian Mixture Models for regime clustering
"""

import logging
import numpy as np
import pandas as pd
from typing import Optional, Tuple, Dict, List
from sklearn.decomposition import PCA
from sklearn.mixture import GaussianMixture
from sklearn.covariance import LedoitWolf
import warnings

logger = logging.getLogger(__name__)


class KritzmanLiTurbulence:
    """
    Kritzman & Li Turbulence Index

    Measures market turbulence using Mahalanobis distance:
    d_t = (r_t - μ)ᵀ · Σ⁻¹ · (r_t - μ) / n

    where:
    - r_t: current period returns vector
    - μ: mean returns vector
    - Σ: covariance matrix
    - n: number of assets
    """

    def __init__(self, window: int = 252, min_periods: int = 100):
        """
        Initialize Kritzman & Li Turbulence calculator.

        Parameters
        ----------
        window : int
            Rolling window size in days (default 252 for 1 year)
        min_periods : int
            Minimum number of periods required for calculation
        """
        self.window = window
        self.min_periods = min_periods

    def calculate(self, returns: pd.DataFrame) -> pd.Series:
        """
        Calculate turbulence index for multi-asset returns.

        Parameters
        ----------
        returns : pd.DataFrame
            DataFrame with asset returns (columns = assets, index = dates)

        Returns
        -------
        pd.Series
            Turbulence index time series
        """
        turbulence = pd.Series(index=returns.index, dtype=float)
        n_assets = len(returns.columns)

        for i in range(len(returns)):
            if i < self.min_periods - 1:
                turbulence.iloc[i] = np.nan
                continue

            # Get rolling window
            start_idx = max(0, i - self.window + 1)
            window_returns = returns.iloc[start_idx:i+1]

            if len(window_returns) < self.min_periods:
                turbulence.iloc[i] = np.nan
                continue

            # Calculate mean and covariance
            mean_returns = window_returns.mean()

            # Use Ledoit-Wolf shrinkage for more stable covariance estimation
            try:
                lw = LedoitWolf()
                cov_matrix = lw.fit(window_returns.values).covariance_
            except:
                # Fallback to sample covariance with small regularization
                cov_matrix = window_returns.cov().values
                cov_matrix += np.eye(n_assets) * 1e-6

            # Current period deviation from mean
            current_return = returns.iloc[i].values
            deviation = current_return - mean_returns.values

            # Calculate Mahalanobis distance
            try:
                cov_inv = np.linalg.inv(cov_matrix)
                mahal_dist = deviation @ cov_inv @ deviation
                turbulence.iloc[i] = mahal_dist / n_assets
            except np.linalg.LinAlgError:
                # Handle singular matrix
                turbulence.iloc[i] = np.nan

        return turbulence


class AbsorptionRatio:
    """
    Absorption Ratio - PCA-based systemic risk measure

    Measures the fraction of total variance explained by a fixed number
    of principal components (typically top 1/5 of eigenvectors).

    High absorption ratio indicates that systematic risk dominates,
    suggesting markets are more vulnerable to contagion.
    """

    def __init__(self, window: int = 500, min_periods: int = 200, fraction_components: float = 0.2):
        """
        Initialize Absorption Ratio calculator.

        Parameters
        ----------
        window : int
            Rolling window size in days (default 500)
        min_periods : int
            Minimum number of periods required
        fraction_components : float
            Fraction of components to use (default 0.2 for top 1/5)
        """
        self.window = window
        self.min_periods = min_periods
        self.fraction_components = fraction_components

    def calculate(self, returns: pd.DataFrame) -> pd.Series:
        """
        Calculate absorption ratio for multi-asset returns.

        Parameters
        ----------
        returns : pd.DataFrame
            DataFrame with asset returns (columns = assets, index = dates)

        Returns
        -------
        pd.Series
            Absorption ratio time series
        """
        absorption_ratio = pd.Series(index=returns.index, dtype=float)
        n_assets = len(returns.columns)
        n_components = max(1, int(n_assets * self.fraction_components))

        for i in range(len(returns)):
            if i < self.min_periods - 1:
                absorption_ratio.iloc[i] = np.nan
                continue

            # Get rolling window
            start_idx = max(0, i - self.window + 1)
            window_returns = returns.iloc[start_idx:i+1]

            if len(window_returns) < self.min_periods:
                absorption_ratio.iloc[i] = np.nan
                continue

            # Standardize returns
            standardized = (window_returns - window_returns.mean()) / window_returns.std()

            # Handle NaN or infinite values
            if standardized.isnull().any().any() or np.isinf(standardized.values).any():
                absorption_ratio.iloc[i] = np.nan
                continue

            try:
                # Perform PCA
                pca = PCA(n_components=n_components)
                pca.fit(standardized.dropna())

                # Calculate absorption ratio
                # Sum of variance explained by top components / total variance
                ar = pca.explained_variance_ratio_.sum()
                absorption_ratio.iloc[i] = ar

            except Exception as e:
                warnings.warn(f"PCA failed at index {i}: {str(e)}")
                absorption_ratio.iloc[i] = np.nan

        return absorption_ratio


class RegimeClustering:
    """
    Gaussian Mixture Models for market regime identification

    Uses GMM to cluster market states based on multi-asset features.
    Identifies distinct regimes (e.g., calm, volatile, crisis).
    """

    def __init__(self, n_regimes: int = 3, feature_window: int = 20,
                 covariance_type: str = 'full', random_state: int = 42):
        """
        Initialize regime clustering with GMM.

        Parameters
        ----------
        n_regimes : int
            Number of market regimes to identify (default 3)
        feature_window : int
            Window for calculating rolling features
        covariance_type : str
            GMM covariance type ('full', 'tied', 'diag', 'spherical')
        random_state : int
            Random seed for reproducibility
        """
        self.n_regimes = n_regimes
        self.feature_window = feature_window
        self.covariance_type = covariance_type
        self.random_state = random_state
        self.gmm = None
        self.scaler_mean = None
        self.scaler_std = None

    def _create_features(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Create features for regime clustering.

        Parameters
        ----------
        returns : pd.DataFrame
            Asset returns

        Returns
        -------
        pd.DataFrame
            Feature matrix with rolling statistics
        """
        features = pd.DataFrame(index=returns.index)

        # Rolling volatility (std)
        features['volatility'] = returns.std(axis=1).rolling(
            window=self.feature_window, min_periods=self.feature_window//2
        ).mean()

        # Rolling correlation (mean pairwise correlation)
        def mean_correlation(window_data):
            if len(window_data) < 5:
                return np.nan
            corr_matrix = window_data.corr()
            # Get upper triangle excluding diagonal
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            return corr_matrix.values[mask].mean()

        features['mean_correlation'] = pd.Series(
            [mean_correlation(returns.iloc[max(0, i-self.feature_window+1):i+1])
             for i in range(len(returns))],
            index=returns.index
        )

        # Rolling mean return
        features['mean_return'] = returns.mean(axis=1).rolling(
            window=self.feature_window, min_periods=self.feature_window//2
        ).mean()

        # Volatility of volatility
        rolling_vol = returns.std(axis=1)
        features['vol_of_vol'] = rolling_vol.rolling(
            window=self.feature_window, min_periods=self.feature_window//2
        ).std()

        # Downside volatility
        downside_returns = returns.copy()
        downside_returns[downside_returns > 0] = 0
        features['downside_vol'] = downside_returns.std(axis=1).rolling(
            window=self.feature_window, min_periods=self.feature_window//2
        ).mean()

        return features

    def fit(self, returns: pd.DataFrame) -> 'RegimeClustering':
        """
        Fit GMM to historical data to learn regimes.

        Parameters
        ----------
        returns : pd.DataFrame
            Historical asset returns for training

        Returns
        -------
        self
        """
        # Create features
        features = self._create_features(returns)

        # Remove NaN rows
        features_clean = features.dropna()

        if len(features_clean) < self.n_regimes * 10:
            raise ValueError(
                f"Insufficient data points ({len(features_clean)}) "
                f"for {self.n_regimes} regimes"
            )

        # Standardize features
        self.scaler_mean = features_clean.mean()
        self.scaler_std = features_clean.std()
        features_scaled = (features_clean - self.scaler_mean) / self.scaler_std

        # Fit GMM
        self.gmm = GaussianMixture(
            n_components=self.n_regimes,
            covariance_type=self.covariance_type,
            random_state=self.random_state,
            max_iter=200,
            n_init=10
        )
        self.gmm.fit(features_scaled.values)

        return self

    def predict(self, returns: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Predict regimes for given returns.

        Parameters
        ----------
        returns : pd.DataFrame
            Asset returns to classify

        Returns
        -------
        regimes : pd.Series
            Predicted regime labels
        probabilities : pd.DataFrame
            Probability of each regime
        """
        if self.gmm is None:
            raise ValueError("Model must be fitted before prediction. Call fit() first.")

        # Create features
        features = self._create_features(returns)

        # Initialize results
        regimes = pd.Series(index=returns.index, dtype=float)
        probabilities = pd.DataFrame(
            index=returns.index,
            columns=[f'regime_{i}' for i in range(self.n_regimes)],
            dtype=float
        )

        # Predict for each valid row
        for idx in features.index:
            if features.loc[idx].isnull().any():
                regimes.loc[idx] = np.nan
                probabilities.loc[idx] = np.nan
            else:
                # Standardize
                features_scaled = (features.loc[idx] - self.scaler_mean) / self.scaler_std
                features_array = features_scaled.values.reshape(1, -1)

                # Predict
                regimes.loc[idx] = self.gmm.predict(features_array)[0]
                probabilities.loc[idx] = self.gmm.predict_proba(features_array)[0]

        return regimes, probabilities

    def get_regime_characteristics(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Get characteristics of each identified regime.

        Parameters
        ----------
        returns : pd.DataFrame
            Historical returns used for training

        Returns
        -------
        pd.DataFrame
            Characteristics of each regime
        """
        if self.gmm is None:
            raise ValueError("Model must be fitted first.")

        features = self._create_features(returns)
        regimes, _ = self.predict(returns)

        characteristics = []
        for regime_id in range(self.n_regimes):
            regime_mask = regimes == regime_id
            regime_features = features[regime_mask]

            char = {
                'regime': regime_id,
                'n_observations': regime_mask.sum(),
                'frequency': regime_mask.sum() / len(regimes.dropna()),
                'mean_volatility': regime_features['volatility'].mean(),
                'mean_correlation': regime_features['mean_correlation'].mean(),
                'mean_return': regime_features['mean_return'].mean(),
                'mean_vol_of_vol': regime_features['vol_of_vol'].mean(),
                'mean_downside_vol': regime_features['downside_vol'].mean()
            }
            characteristics.append(char)

        return pd.DataFrame(characteristics)


def calculate_tier3_indicators(
    returns: pd.DataFrame,
    turbulence_window: int = 252,
    absorption_window: int = 500,
    n_regimes: int = 3,
    clustering_train_window: int = 756,
    clustering_refit_days: int = 5
) -> Dict[str, pd.Series]:
    """
    Calculate all Tier 3 indicators for multi-asset returns.

    Uses expanding window for regime clustering to avoid look-ahead bias.
    Each date's prediction uses only data available up to that point.

    Parameters
    ----------
    returns : pd.DataFrame
        Multi-asset returns (columns = assets, index = dates)
    turbulence_window : int
        Window for Kritzman-Li turbulence (default 252)
    absorption_window : int
        Window for absorption ratio (default 500)
    n_regimes : int
        Number of regimes for GMM clustering (default 3)
    clustering_train_window : int
        Minimum window for initial GMM training (default 756 = 3 years)
    clustering_refit_days : int
        Refit GMM every N days instead of daily (default 5 for weekly).
        Set to 1 for daily refitting (slow but most accurate).
        Higher values are faster but less responsive to regime changes.

    Returns
    -------
    dict
        Dictionary containing:
        - 'turbulence': Kritzman-Li turbulence index
        - 'absorption_ratio': Absorption ratio
        - 'regime': Regime classifications
        - 'regime_probs': Regime probabilities DataFrame
    """
    results = {}

    # Kritzman-Li Turbulence - Already correct (uses rolling windows)
    kl = KritzmanLiTurbulence(window=turbulence_window)
    results['turbulence'] = kl.calculate(returns)

    # Absorption Ratio - Already correct (uses rolling windows)
    ar = AbsorptionRatio(window=absorption_window)
    results['absorption_ratio'] = ar.calculate(returns)

    # Regime Clustering - FIX: Use expanding window to avoid look-ahead bias
    # Refit every N days for performance (daily refitting is very slow)
    regimes = pd.Series(index=returns.index, dtype=float)
    regime_probs = pd.DataFrame(
        index=returns.index,
        columns=[f'regime_{i}' for i in range(n_regimes)],
        dtype=float
    )

    # Calculate how many models we'll fit for progress indication
    valid_range = max(0, len(returns) - clustering_train_window)
    total_fits = (valid_range + clustering_refit_days - 1) // clustering_refit_days
    logger.info(f"Tier 3 Regime Clustering: Refitting every {clustering_refit_days} days (~{total_fits} fits)...")

    # Track the last fitted model to reuse between refits
    last_rc = None
    last_fit_idx = -1
    fits_completed = 0

    # For each date, train on expanding window of data available up to that date
    for i in range(len(returns)):
        if i < clustering_train_window:
            # Not enough data for initial training
            regimes.iloc[i] = np.nan
            regime_probs.iloc[i] = np.nan
            continue

        # Decide whether to refit the model
        should_refit = (
            last_rc is None or  # First fit
            (i - last_fit_idx) >= clustering_refit_days  # Time to refit
        )

        if should_refit:
            # Use expanding window: train on all data UP TO AND INCLUDING current point
            # This is point-in-time correct - we use only data available at time i
            train_data = returns.iloc[:i+1]

            try:
                last_rc = RegimeClustering(n_regimes=n_regimes)
                last_rc.fit(train_data)
                last_fit_idx = i
                fits_completed += 1

                # Show progress
                if fits_completed % 10 == 0 or i == len(returns) - 1:
                    progress_pct = (fits_completed / total_fits * 100) if total_fits > 0 else 0
                    logger.info(f"  Progress: {fits_completed}/{total_fits} fits ({progress_pct:.1f}%) - Date: {returns.index[i].strftime('%Y-%m-%d')}")

            except Exception as e:
                warnings.warn(f"Regime clustering failed at index {i}: {str(e)}")
                regimes.iloc[i] = np.nan
                regime_probs.iloc[i] = np.nan
                continue

        # Predict using current model (newly fitted or previous)
        if last_rc is not None:
            try:
                # Predict on data up to current point
                predict_data = returns.iloc[:i+1]
                regime, probs = last_rc.predict(predict_data)
                regimes.iloc[i] = regime.iloc[-1]
                regime_probs.iloc[i] = probs.iloc[-1]
            except Exception as e:
                warnings.warn(f"Prediction failed at index {i}: {str(e)}")
                regimes.iloc[i] = np.nan
                regime_probs.iloc[i] = np.nan

    logger.info(f"  Completed: {fits_completed} GMM models fitted")

    results['regime'] = regimes
    results['regime_probs'] = regime_probs

    return results
