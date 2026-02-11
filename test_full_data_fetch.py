#!/usr/bin/env python3
"""Test fetching all required tickers for turbulence analysis."""

import sys
sys.path.insert(0, '/home/user/code/turbulence/src')

from dotenv import load_dotenv
from turbulence.database import DatabaseManager
from turbulence.data_fetcher import DataFetcher

# Load environment variables
load_dotenv('/home/user/code/turbulence/.env')


def main():
    print("=" * 80)
    print("Fetching All Required Tickers for Turbulence Analysis")
    print("=" * 80)

    # Initialize
    db = DatabaseManager()
    fetcher = DataFetcher()

    # Fetch all default tickers from 2020 onwards (reasonable historical data)
    print(f"\nFetching tickers: {', '.join(fetcher.DEFAULT_TICKERS)}")
    print("Date range: 2020-01-01 to present")
    print()

    with db.get_connection() as conn:
        result = fetcher.fetch_and_store(
            conn,
            tickers=fetcher.DEFAULT_TICKERS,
            start_date='2020-01-01'
        )

        print("\n" + "=" * 80)
        print("Fetch Results:")
        print("=" * 80)
        for key, value in result.items():
            print(f"  {key}: {value}")

        # Query database for summary
        print("\n" + "=" * 80)
        print("Database Summary:")
        print("=" * 80)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    ticker,
                    COUNT(*) as row_count,
                    MIN(date) as first_date,
                    MAX(date) as last_date,
                    COUNT(DISTINCT date) as unique_dates
                FROM price_data
                GROUP BY ticker
                ORDER BY ticker
            """)

            results = cur.fetchall()
            print(f"\n{'Ticker':<10} {'Rows':<10} {'First Date':<12} {'Last Date':<12} {'Unique Dates':<12}")
            print("-" * 80)
            for row in results:
                print(f"{row[0]:<10} {row[1]:<10} {str(row[2]):<12} {str(row[3]):<12} {row[4]:<12}")

            # Total statistics
            cur.execute("SELECT COUNT(*) FROM price_data")
            total_rows = cur.fetchone()[0]
            print("-" * 80)
            print(f"Total rows in price_data: {total_rows}")

    db.close()
    print("\n" + "=" * 80)
    print("All tickers fetched and stored successfully!")
    print("=" * 80)


if __name__ == '__main__':
    main()
