"""
Turbulence: A financial market turbulence detection system.

This package provides tools for detecting financial market turbulence using
Hidden Markov Models and various statistical indicators.
"""

__version__ = "0.1.0"

from turbulence.config import get_config, setup_logging, get_logger
from turbulence.database import DatabaseManager, get_db_manager
from turbulence.utils import (
    DatabaseConnectionError,
    APIRateLimitError,
    MissingDataError,
    NumericalInstabilityError,
    retry_on_failure,
    rate_limit,
    safe_database_operation,
)

from .tier1 import (
    classify_vix_regime,
    calculate_vix_term_structure,
    classify_vix_term_structure,
    calculate_garman_klass_volatility,
    classify_by_percentile,
    calculate_tier1_indicators,
)

from .backtest import run_walk_forward, summarize_backtest
from .report import generate_report
