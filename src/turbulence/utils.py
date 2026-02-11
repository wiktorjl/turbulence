"""Utility functions and error handling for turbulence tracking system."""

import time
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

import numpy as np
import psycopg2

from turbulence.config import get_config, get_logger

logger = get_logger(__name__)

T = TypeVar('T')


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class APIRateLimitError(Exception):
    """Raised when API rate limit is exceeded."""
    pass


class MissingDataError(Exception):
    """Raised when required data is missing."""
    pass


class NumericalInstabilityError(Exception):
    """Raised when numerical computation becomes unstable."""
    pass


def retry_on_failure(
    max_retries: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Decorator to retry a function on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts. Uses config default if None.
        backoff_factor: Multiplier for wait time between retries. Uses config default if None.
        exceptions: Tuple of exception types to catch and retry on.

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = get_config()
            retries = max_retries if max_retries is not None else config.api_max_retries
            backoff = backoff_factor if backoff_factor is not None else config.api_retry_backoff

            last_exception = None
            for attempt in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < retries:
                        wait_time = backoff ** attempt
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{retries + 1}): {e}. "
                            f"Retrying in {wait_time:.2f}s..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(f"{func.__name__} failed after {retries + 1} attempts")

            raise last_exception

        return wrapper
    return decorator


def rate_limit(delay: Optional[float] = None) -> Callable:
    """
    Decorator to rate limit function calls.

    Args:
        delay: Minimum time in seconds between calls. Uses config default if None.

    Returns:
        Decorated function with rate limiting
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        last_called = [0.0]

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = get_config()
            wait_time = delay if delay is not None else config.api_rate_limit_delay

            elapsed = time.time() - last_called[0]
            if elapsed < wait_time:
                time.sleep(wait_time - elapsed)

            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result

        return wrapper
    return decorator


def safe_database_operation(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to handle database connection errors gracefully.

    Args:
        func: Function that performs database operations

    Returns:
        Decorated function with error handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except psycopg2.OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseConnectionError(
                f"Failed to connect to database. Please check your DATABASE_URL configuration."
            ) from e
        except psycopg2.IntegrityError as e:
            logger.error(f"Database integrity error: {e}")
            raise
        except psycopg2.Error as e:
            logger.error(f"Database error: {e}")
            raise

    return wrapper


def check_covariance_matrix(cov_matrix: np.ndarray, name: str = "covariance") -> np.ndarray:
    """
    Check and fix numerical issues with covariance matrices.

    Args:
        cov_matrix: Covariance matrix to check
        name: Name of the matrix for logging

    Returns:
        Regularized covariance matrix if needed

    Raises:
        NumericalInstabilityError: If matrix is severely ill-conditioned
    """
    if not np.all(np.isfinite(cov_matrix)):
        logger.error(f"{name} matrix contains NaN or Inf values")
        raise NumericalInstabilityError(f"{name} matrix contains non-finite values")

    if not np.allclose(cov_matrix, cov_matrix.T):
        logger.warning(f"{name} matrix is not symmetric, symmetrizing")
        cov_matrix = (cov_matrix + cov_matrix.T) / 2

    eigenvalues = np.linalg.eigvalsh(cov_matrix)

    if np.any(eigenvalues <= 0):
        logger.warning(
            f"{name} matrix is not positive definite. "
            f"Min eigenvalue: {eigenvalues.min():.6e}. Applying regularization."
        )

        epsilon = 1e-6 * np.abs(eigenvalues.max())
        if epsilon < 1e-8:
            epsilon = 1e-8

        cov_matrix = cov_matrix + epsilon * np.eye(cov_matrix.shape[0])

        eigenvalues_fixed = np.linalg.eigvalsh(cov_matrix)
        if np.any(eigenvalues_fixed <= 0):
            raise NumericalInstabilityError(
                f"{name} matrix is severely ill-conditioned and cannot be regularized"
            )

    condition_number = np.linalg.cond(cov_matrix)
    if condition_number > 1e10:
        logger.warning(f"{name} matrix has high condition number: {condition_number:.2e}")

    return cov_matrix


def handle_missing_data(data: Any, field_name: str, allow_empty: bool = False) -> Any:
    """
    Handle missing or invalid data with appropriate error messages.

    Args:
        data: Data to check
        field_name: Name of the field for error messages
        allow_empty: Whether empty/None values are acceptable

    Returns:
        The data if valid

    Raises:
        MissingDataError: If data is missing and not allowed
    """
    if data is None or (hasattr(data, '__len__') and len(data) == 0):
        if not allow_empty:
            raise MissingDataError(f"Missing required data: {field_name}")

    if isinstance(data, (np.ndarray, list)) and len(data) > 0:
        if isinstance(data, np.ndarray):
            if not np.all(np.isfinite(data)):
                raise MissingDataError(
                    f"{field_name} contains NaN or Inf values"
                )

    return data


def validate_date_range(start_date: Any, end_date: Any) -> None:
    """
    Validate that date range is valid.

    Args:
        start_date: Start date
        end_date: End date

    Raises:
        ValueError: If date range is invalid
    """
    if start_date >= end_date:
        raise ValueError(
            f"Invalid date range: start_date ({start_date}) must be before end_date ({end_date})"
        )


def format_error_message(error: Exception, context: str = "") -> str:
    """
    Format error message for user-friendly display.

    Args:
        error: Exception to format
        context: Additional context about where the error occurred

    Returns:
        Formatted error message
    """
    error_type = type(error).__name__
    message = str(error)

    if context:
        return f"[{context}] {error_type}: {message}"
    return f"{error_type}: {message}"


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if division by zero.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Value to return if denominator is zero

    Returns:
        Result of division or default value
    """
    if denominator == 0 or not np.isfinite(denominator):
        return default
    result = numerator / denominator
    if not np.isfinite(result):
        return default
    return result


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between minimum and maximum bounds.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))
