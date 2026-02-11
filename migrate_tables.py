#!/usr/bin/env python3
"""
Migration script to rename old tables to new turbulence_ prefix and drop price_data.

This script:
1. Migrates data from old tables to new turbulence_ prefixed tables
2. Drops old tables (price_data, volatility_metrics, regime_classifications, composite_scores)
3. Creates new turbulence_ tables if they don't exist

Safe to run multiple times (uses IF EXISTS / IF NOT EXISTS).
"""

import sys
import psycopg2
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables")
    sys.exit(1)


def main():
    print("=" * 80)
    print("Turbulence Table Migration Script")
    print("=" * 80)
    print()
    print("This will:")
    print("  1. Create new turbulence_ prefixed tables")
    print("  2. Migrate data from old tables to new tables")
    print("  3. Drop old tables (price_data, volatility_metrics, regime_classifications, composite_scores)")
    print()
    response = input("Continue? (yes/no): ")

    if response.lower() not in ['yes', 'y']:
        print("Migration cancelled.")
        sys.exit(0)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # Check if old tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('price_data', 'volatility_metrics', 'regime_classifications', 'composite_scores')
            ORDER BY table_name
        """)
        old_tables = [row[0] for row in cur.fetchall()]

        if not old_tables:
            print("\n✓ No old tables found. Nothing to migrate.")
            conn.close()
            return

        print(f"\nFound old tables to migrate: {', '.join(old_tables)}")

        # 1. Create new turbulence_ tables
        print("\n1. Creating new turbulence_ tables...")

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

        print("   ✓ New tables created")

        # 2. Migrate data from old tables to new tables
        print("\n2. Migrating data from old tables to new tables...")

        if 'volatility_metrics' in old_tables:
            cur.execute("SELECT COUNT(*) FROM volatility_metrics")
            count = cur.fetchone()[0]
            if count > 0:
                cur.execute("""
                    INSERT INTO turbulence_volatility_metrics
                    (ticker, date, garman_klass_vol, parkinson_vol, rogers_satchell_vol,
                     yang_zhang_vol, close_to_close_vol, vol_percentile, created_at)
                    SELECT ticker, date, garman_klass_vol, parkinson_vol, rogers_satchell_vol,
                           yang_zhang_vol, close_to_close_vol, vol_percentile, created_at
                    FROM volatility_metrics
                    ON CONFLICT (ticker, date) DO NOTHING
                """)
                print(f"   ✓ Migrated {count} rows from volatility_metrics")
            else:
                print("   • volatility_metrics is empty, skipping")

        if 'regime_classifications' in old_tables:
            cur.execute("SELECT COUNT(*) FROM regime_classifications")
            count = cur.fetchone()[0]
            if count > 0:
                cur.execute("""
                    INSERT INTO turbulence_regime_classifications
                    (date, vix_level, vix3m_level, vix_term_structure_ratio, vix_regime,
                     realized_vol_percentile, garch_conditional_vol, turbulence_index,
                     hmm_state, hmm_prob_low, hmm_prob_normal, hmm_prob_high,
                     absorption_ratio, created_at)
                    SELECT date, vix_level, vix3m_level, vix_term_structure_ratio, vix_regime,
                           realized_vol_percentile, garch_conditional_vol, turbulence_index,
                           hmm_state, hmm_prob_low, hmm_prob_normal, hmm_prob_high,
                           absorption_ratio, created_at
                    FROM regime_classifications
                    ON CONFLICT (date) DO NOTHING
                """)
                print(f"   ✓ Migrated {count} rows from regime_classifications")
            else:
                print("   • regime_classifications is empty, skipping")

        if 'composite_scores' in old_tables:
            cur.execute("SELECT COUNT(*) FROM composite_scores")
            count = cur.fetchone()[0]
            if count > 0:
                cur.execute("""
                    INSERT INTO turbulence_composite_scores
                    (date, vix_component, vix_term_component, realized_vol_component,
                     turbulence_component, garch_component, composite_score, regime_label, created_at)
                    SELECT date, vix_component, vix_term_component, realized_vol_component,
                           turbulence_component, garch_component, composite_score, regime_label, created_at
                    FROM composite_scores
                    ON CONFLICT (date) DO NOTHING
                """)
                print(f"   ✓ Migrated {count} rows from composite_scores")
            else:
                print("   • composite_scores is empty, skipping")

        # 3. Drop old tables
        print("\n3. Dropping old tables...")

        cur.execute("""
            DROP TABLE IF EXISTS composite_scores CASCADE;
            DROP TABLE IF EXISTS regime_classifications CASCADE;
            DROP TABLE IF EXISTS volatility_metrics CASCADE;
            DROP TABLE IF EXISTS price_data CASCADE;
        """)

        print("   ✓ Dropped old tables")

        # 4. Verify migration
        print("\n4. Verifying migration...")

        cur.execute("""
            SELECT
                (SELECT COUNT(*) FROM turbulence_volatility_metrics) as volatility_count,
                (SELECT COUNT(*) FROM turbulence_regime_classifications) as regime_count,
                (SELECT COUNT(*) FROM turbulence_composite_scores) as composite_count
        """)
        counts = cur.fetchone()

        print(f"   turbulence_volatility_metrics: {counts[0]} rows")
        print(f"   turbulence_regime_classifications: {counts[1]} rows")
        print(f"   turbulence_composite_scores: {counts[2]} rows")

        # Commit changes
        conn.commit()
        cur.close()
        conn.close()

        print("\n" + "=" * 80)
        print("✓ Migration completed successfully!")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Test the system: python -m turbulence.cli status")
        print("  2. Fetch new data: python -m turbulence.cli fetch-data")
        print("  3. Compute indicators: python -m turbulence.cli compute")

    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        if conn:
            conn.rollback()
            conn.close()
        sys.exit(1)


if __name__ == '__main__':
    main()
