"""Configuration management for turbulence tracking system."""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


class Config:
    """Central configuration management for the turbulence system."""

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration by loading from environment.

        Args:
            env_file: Path to .env file. If None, searches for .env in project root.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            project_root = Path(__file__).parent.parent.parent
            env_path = project_root / '.env'
            if env_path.exists():
                load_dotenv(env_path)

        self._validate_config()

    def _validate_config(self) -> None:
        """Validate that required configuration is present."""
        missing = []

        if not self.database_url:
            missing.append('DATABASE_URL')

        if not self.polygon_api_key:
            missing.append('POLYGON_API_KEY')

        if missing:
            raise ConfigurationError(
                f"Missing required configuration: {', '.join(missing)}. "
                f"Please set these in your .env file or environment variables."
            )

    @property
    def database_url(self) -> str:
        """PostgreSQL database connection URL."""
        return os.getenv('DATABASE_URL', '')

    @property
    def polygon_api_key(self) -> str:
        """Polygon.io API key."""
        return os.getenv('POLYGON_API_KEY', '')

    @property
    def polygon_s3_access_key(self) -> Optional[str]:
        """Polygon.io S3 access key (optional)."""
        return os.getenv('POLYGON_S3_ACCESS_KEY')

    @property
    def polygon_s3_secret_key(self) -> Optional[str]:
        """Polygon.io S3 secret key (optional)."""
        return os.getenv('POLYGON_S3_SECRET_KEY')

    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        return os.getenv('LOG_LEVEL', 'INFO').upper()

    @property
    def log_format(self) -> str:
        """Logging format string."""
        return os.getenv(
            'LOG_FORMAT',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    @property
    def db_pool_min(self) -> int:
        """Minimum database connection pool size."""
        return int(os.getenv('DB_POOL_MIN', '1'))

    @property
    def db_pool_max(self) -> int:
        """Maximum database connection pool size."""
        return int(os.getenv('DB_POOL_MAX', '10'))

    @property
    def api_rate_limit_delay(self) -> float:
        """Delay between API calls in seconds to respect rate limits."""
        return float(os.getenv('API_RATE_LIMIT_DELAY', '0.2'))

    @property
    def api_max_retries(self) -> int:
        """Maximum number of retries for failed API calls."""
        return int(os.getenv('API_MAX_RETRIES', '3'))

    @property
    def api_retry_backoff(self) -> float:
        """Backoff multiplier for retrying API calls."""
        return float(os.getenv('API_RETRY_BACKOFF', '2.0'))


_config_instance: Optional[Config] = None


def get_config() -> Config:
    """
    Get singleton configuration instance.

    Returns:
        Global Config instance

    Raises:
        ConfigurationError: If required configuration is missing
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def setup_logging(config: Optional[Config] = None) -> None:
    """
    Configure logging for the entire application.

    Args:
        config: Config instance. If None, uses global config.
    """
    if config is None:
        config = get_config()

    level = getattr(logging, config.log_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format=config.log_format,
        handlers=[
            logging.StreamHandler(),
        ]
    )

    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('psycopg2').setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
