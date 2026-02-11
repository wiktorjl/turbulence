#!/usr/bin/env python3
"""Test script for database setup and data fetching."""

import sys
import os
sys.path.insert(0, '/home/user/code/turbulence/src')

from dotenv import load_dotenv
from turbulence.database import DatabaseManager
from turbulence.data_fetcher import DataFetcher
from datetime import datetime, timedelta

# Load environment variables
load_dotenv('/home/user/code/turbulence/.env')


def main():
    print("=" * 80)
    print("Testing Database Setup and Data Fetching")
    print("=" * 80)

    # Initialize database manager
    print("\n1. Initializing database manager...")
    db = DatabaseManager()
    print("   Database manager initialized successfully")

    # Create schema
    print("\n2. Creating database schema...")
    db.create_schema()
    print("   Database schema created successfully")

    # Verify tables exist
    print("\n3. Verifying tables exist...")
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            print(f"   Found {len(tables)} tables:")
            for table in tables:
                print(f"     - {table}")

    # Initialize data fetcher
    print("\n4. Initializing data fetcher...")
    fetcher = DataFetcher()
    print(f"   Using Polygon API key: {fetcher.polygon_api_key[:10]}..." if fetcher.polygon_api_key else "   No Polygon API key found")

    # Fetch sample data (last 30 days)
    print("\n5. Fetching sample data (last 30 days)...")
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

    # Test with a single ticker first
    print(f"\n   Testing SPY from {start_date} to {end_date}...")
    spy_data = fetcher.fetch_ticker_data('SPY', start_date, end_date)
    if spy_data is not None:
        print(f"   Successfully fetched {len(spy_data)} rows for SPY")
        print(f"\n   Sample data (first 3 rows):")
        print(spy_data.head(3).to_string(index=False))
    else:
        print("   Failed to fetch SPY data")

    # Store the data
    if spy_data is not None:
        print("\n6. Storing data in database...")
        with db.get_connection() as conn:
            inserted, updated = fetcher.store_price_data(conn, spy_data)
            print(f"   Inserted: {inserted} rows")
            print(f"   Updated: {updated} rows")

        # Verify stored data
        print("\n7. Verifying stored data...")
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ticker, COUNT(*) as count, MIN(date) as min_date, MAX(date) as max_date
                    FROM price_data
                    GROUP BY ticker
                    ORDER BY ticker
                """)
                results = cur.fetchall()
                print(f"   Data in database:")
                for row in results:
                    print(f"     {row[0]}: {row[1]} rows, {row[2]} to {row[3]}")

    # Clean up
    print("\n8. Closing database connections...")
    db.close()
    print("   Database connections closed")

    print("\n" + "=" * 80)
    print("Test completed successfully!")
    print("=" * 80)


if __name__ == '__main__':
    main()
