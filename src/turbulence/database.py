"""Database schema and connection management for turbulence tracking system."""

from contextlib import contextmanager
from typing import Generator, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extensions import connection

from turbulence.config import get_config, get_logger
from turbulence.utils import safe_database_operation, DatabaseConnectionError

logger = get_logger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and schema operations."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_conn: Optional[int] = None,
        max_conn: Optional[int] = None
    ):
        """
        Initialize database manager with connection pooling.

        Args:
            database_url: PostgreSQL connection URL. If None, reads from config.
            min_conn: Minimum number of connections in pool. Uses config default if None.
            max_conn: Maximum number of connections in pool. Uses config default if None.
        """
        config = get_config()

        self.database_url = database_url or config.database_url
        if not self.database_url:
            raise DatabaseConnectionError(
                "DATABASE_URL not provided. Please set it in .env or environment variables."
            )

        min_conn = min_conn if min_conn is not None else config.db_pool_min
        max_conn = max_conn if max_conn is not None else config.db_pool_max

        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                min_conn,
                max_conn,
                self.database_url
            )
            logger.info(f"Database connection pool created (min={min_conn}, max={max_conn})")
        except psycopg2.Error as e:
            logger.error(f"Failed to create database connection pool: {e}")
            raise DatabaseConnectionError(
                f"Could not connect to database. Please verify DATABASE_URL: {e}"
            ) from e

    @contextmanager
    def get_connection(self) -> Generator[connection, None, None]:
        """
        Context manager for database connections.

        Yields:
            PostgreSQL connection from pool

        Raises:
            DatabaseConnectionError: If connection cannot be obtained
        """
        conn = None
        try:
            conn = self.pool.getconn()
            if conn is None:
                raise DatabaseConnectionError("Failed to get connection from pool")
            yield conn
            conn.commit()
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database operation failed: {e}")
            raise
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Unexpected error during database operation: {e}")
            raise
        finally:
            if conn:
                self.pool.putconn(conn)

    @safe_database_operation
    def create_schema(self) -> None:
        """
        Create turbulence-specific database tables if they don't exist.

        Note: Uses existing stock_prices table for price data.
        Only creates turbulence-specific tables with turbulence_ prefix.

        Raises:
            DatabaseConnectionError: If database connection fails
        """
        logger.info("Creating turbulence database schema...")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Volatility metrics table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS turbulence_volatility_metrics (
                        id SERIAL PRIMARY KEY,
                        ticker VARCHAR(20) NOT NULL,
                        date DATE NOT NULL,
                        garman_klass_vol NUMERIC(12, 6),
                        parkinson_vol NUMERIC(12, 6),
                        rogers_satchell_vol NUMERIC(12, 6),
                        yang_zhang_vol NUMERIC(12, 6),
                        close_to_close_vol NUMERIC(12, 6),
                        vol_percentile NUMERIC(5, 4),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(ticker, date)
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turbulence_volatility_ticker_date
                    ON turbulence_volatility_metrics(ticker, date DESC)
                """)

                # Regime classifications table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS turbulence_regime_classifications (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL UNIQUE,
                        vix_level NUMERIC(8, 4),
                        vix3m_level NUMERIC(8, 4),
                        vix_term_structure_ratio NUMERIC(8, 6),
                        vix_regime VARCHAR(20),
                        realized_vol_percentile NUMERIC(5, 4),
                        garch_conditional_vol NUMERIC(12, 6),
                        turbulence_index NUMERIC(12, 6),
                        hmm_state INTEGER,
                        hmm_prob_low NUMERIC(5, 4),
                        hmm_prob_normal NUMERIC(5, 4),
                        hmm_prob_high NUMERIC(5, 4),
                        absorption_ratio NUMERIC(5, 4),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turbulence_regime_date
                    ON turbulence_regime_classifications(date DESC)
                """)

                # Composite scores table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS turbulence_composite_scores (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL UNIQUE,
                        vix_component NUMERIC(5, 4),
                        vix_term_component NUMERIC(5, 4),
                        realized_vol_component NUMERIC(5, 4),
                        turbulence_component NUMERIC(5, 4),
                        garch_component NUMERIC(5, 4),
                        composite_score NUMERIC(5, 4),
                        regime_label VARCHAR(20),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_turbulence_composite_date
                    ON turbulence_composite_scores(date DESC)
                """)

        logger.info("Turbulence database schema created successfully")

    @safe_database_operation
    def drop_all_tables(self) -> None:
        """
        Drop all turbulence-specific tables. Use with caution!

        Note: Does NOT drop stock_prices table (shared resource).

        Raises:
            DatabaseConnectionError: If database connection fails
        """
        logger.warning("Dropping turbulence database tables...")
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    DROP TABLE IF EXISTS turbulence_composite_scores CASCADE;
                    DROP TABLE IF EXISTS turbulence_regime_classifications CASCADE;
                    DROP TABLE IF EXISTS turbulence_volatility_metrics CASCADE;
                """)
        logger.info("Turbulence database tables dropped")

    def close(self) -> None:
        """Close all connections in the pool."""
        if self.pool:
            self.pool.closeall()


def get_db_manager() -> DatabaseManager:
    """
    Factory function to create DatabaseManager instance.

    Returns:
        Configured DatabaseManager instance
    """
    return DatabaseManager()
