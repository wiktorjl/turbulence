"""Upload parquet results to PostgreSQL database.

Reads composite scores and regime classifications from parquet files
and upserts them into the existing turbulence PostgreSQL tables.
"""

import os
from datetime import datetime

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from turbulence import storage
from turbulence.config import get_logger

logger = get_logger(__name__)


def get_db_connection():
    """Create a PostgreSQL connection from DATABASE_URL env var."""
    url = os.getenv('DATABASE_URL')
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Add it to your .env file, e.g.:\n"
            "  DATABASE_URL=postgresql://user:pass@localhost:5432/dbname"
        )
    return psycopg2.connect(url)


def upload_composite_scores(conn, df: pd.DataFrame) -> int:
    """Upsert composite scores into turbulence_composite_scores.

    Parameters
    ----------
    conn : psycopg2 connection
    df : pd.DataFrame
        Composite scores from parquet.

    Returns
    -------
    int
        Number of rows upserted.
    """
    if df.empty:
        return 0

    col_map = {
        'date': 'date',
        'composite_score': 'composite_score',
        'regime_label': 'regime_label',
        'vix_component': 'vix_component',
        'vix_term_component': 'vix_term_component',
        'realized_vol_component': 'realized_vol_component',
        'turbulence_component': 'turbulence_component',
        'garch_component': 'garch_component',
    }

    db_cols = [v for v in col_map.values() if col_map.get(v, v) in col_map.values()]
    parquet_cols = list(col_map.keys())

    # Only include columns that exist in the dataframe
    available = [(p, d) for p, d in col_map.items() if p in df.columns]
    parquet_cols = [p for p, _ in available]
    db_cols = [d for _, d in available]

    subset = df[parquet_cols].copy()
    subset.columns = db_cols
    subset['date'] = pd.to_datetime(subset['date']).dt.date

    cur = conn.cursor()

    # Delete existing rows for dates we're about to insert
    dates = list(subset['date'].unique())
    cur.execute(
        "DELETE FROM turbulence_composite_scores WHERE date = ANY(%s)",
        (dates,)
    )

    cols_str = ', '.join(db_cols)
    template = '(' + ', '.join(['%s'] * len(db_cols)) + ')'

    rows = [tuple(row) for row in subset.itertuples(index=False, name=None)]
    execute_values(
        cur,
        f"INSERT INTO turbulence_composite_scores ({cols_str}) VALUES %s",
        rows,
        template=template,
    )

    conn.commit()
    logger.info(f"Upserted {len(rows)} composite score rows")
    return len(rows)


def upload_regime_classifications(conn, df: pd.DataFrame) -> int:
    """Upsert regime classifications into turbulence_regime_classifications.

    Parameters
    ----------
    conn : psycopg2 connection
    df : pd.DataFrame
        Regime classifications from parquet.

    Returns
    -------
    int
        Number of rows upserted.
    """
    if df.empty:
        return 0

    col_map = {
        'date': 'date',
        'vix_level': 'vix_level',
        'vix3m_level': 'vix3m_level',
        'vix_term_structure_ratio': 'vix_term_structure_ratio',
        'vix_regime': 'vix_regime',
    }

    available = [(p, d) for p, d in col_map.items() if p in df.columns]
    parquet_cols = [p for p, _ in available]
    db_cols = [d for _, d in available]

    subset = df[parquet_cols].copy()
    subset.columns = db_cols
    subset['date'] = pd.to_datetime(subset['date']).dt.date

    cur = conn.cursor()

    dates = list(subset['date'].unique())
    cur.execute(
        "DELETE FROM turbulence_regime_classifications WHERE date = ANY(%s)",
        (dates,)
    )

    cols_str = ', '.join(db_cols)
    template = '(' + ', '.join(['%s'] * len(db_cols)) + ')'

    rows = [tuple(row) for row in subset.itertuples(index=False, name=None)]
    execute_values(
        cur,
        f"INSERT INTO turbulence_regime_classifications ({cols_str}) VALUES %s",
        rows,
        template=template,
    )

    conn.commit()
    logger.info(f"Upserted {len(rows)} regime classification rows")
    return len(rows)


def upload_all(start_date=None, end_date=None):
    """Upload all parquet results to PostgreSQL.

    Parameters
    ----------
    start_date : str or datetime, optional
        Only upload data from this date forward.
    end_date : str or datetime, optional
        Only upload data up to this date.

    Returns
    -------
    dict
        Counts of rows uploaded per table.
    """
    conn = get_db_connection()
    try:
        counts = {}

        composite_df = storage.load_composite_scores(start_date, end_date)
        counts['composite_scores'] = upload_composite_scores(conn, composite_df)

        regime_df = storage.load_regime_classifications(start_date, end_date)
        counts['regime_classifications'] = upload_regime_classifications(conn, regime_df)

        return counts
    finally:
        conn.close()
