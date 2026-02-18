# Database Layer Documentation

## Overview

The database layer provides PostgreSQL schema management and data fetching capabilities for the turbulence tracking system.

**Important:** This system uses your existing `stock_prices` table for price data and creates three turbulence-specific tables with the `turbulence_` prefix.

## Components

### 1. Database Module (`src/turbulence/database.py`)

Manages PostgreSQL connections and schema operations.

**Key Features:**
- Connection pooling for efficient database access
- Automatic schema creation with proper indexes
- Context manager for safe connection handling
- Error handling with proper rollback
- Uses existing stock_prices table (no data duplication)

**Database Schema:**

#### `stock_prices` Table (Existing - Not Modified)
Your existing table for OHLCV data.
- `ticker`: Stock symbol (e.g., SPY, ^VIX)
- `date`: Trading date
- `open`, `high`, `low`, `close`: Price data
- `volume`: Trading volume
- `created_at`: Timestamp

#### `turbulence_volatility_metrics` Table (New)
Stores calculated volatility measures.
- `ticker`: Stock symbol
- `date`: Calculation date
- `garman_klass_vol`, `parkinson_vol`, `rogers_satchell_vol`, `yang_zhang_vol`: Various volatility estimators
- `close_to_close_vol`: Traditional close-to-close volatility
- `vol_percentile`: Rolling percentile rank
- Indexed on (ticker, date) for fast queries

#### `turbulence_regime_classifications` Table (New)
Stores regime detection results.
- `date`: Analysis date
- `vix_level`, `vix3m_level`: VIX levels
- `vix_term_structure_ratio`: VIX/VIX3M ratio
- `vix_regime`: Categorized VIX regime
- `realized_vol_percentile`: Realized volatility percentile
- `garch_conditional_vol`: GARCH conditional volatility
- `turbulence_index`: Mahalanobis turbulence index
- `hmm_state`, `hmm_prob_*`: Hidden Markov Model results
- `absorption_ratio`: PCA-based systemic risk measure
- Indexed on date for fast queries

#### `turbulence_composite_scores` Table (New)
Stores final composite turbulence scores.
- `date`: Score date
- `vix_component`, `vix_term_component`, `realized_vol_component`, `turbulence_component`, `garch_component`: Individual weighted components
- `composite_score`: Final score (0-1 scale)
- `regime_label`: Categorized regime (low, normal, elevated, extreme)
- Indexed on date for fast queries

### 2. Data Fetcher Module (`src/turbulence/data_fetcher.py`)

Fetches market data from Polygon.io with yfinance fallback.

**Key Features:**
- Primary data source: Polygon.io API (professional-grade data)
- Fallback source: yfinance (free alternative)
- Automatic retry logic
- Batch fetching for multiple tickers
- Direct database storage with upsert logic

**Default Tickers:**
- SPY: S&P 500 ETF (equity market proxy)
- TLT: 20+ Year Treasury Bond ETF (long-duration bonds)
- GLD: Gold ETF (safe haven asset)
- UUP: US Dollar Index (currency)
- HYG: High Yield Corporate Bond ETF (credit risk)
- ^VIX: CBOE Volatility Index (implied volatility)
- ^VIX3M: CBOE 3-Month Volatility Index (term structure)

## Usage

### Basic Setup

```python
from turbulence.database import DatabaseManager
from turbulence.data_fetcher import DataFetcher

# Initialize
db = DatabaseManager()
fetcher = DataFetcher()

# Create turbulence-specific tables (uses existing stock_prices for price data)
db.create_schema()

# Fetch and store data (stores in existing stock_prices table)
with db.get_connection() as conn:
    result = fetcher.fetch_and_store(
        conn,
        start_date='2020-01-01'
    )
    print(result)

# Close connections
db.close()
```

### Migrating from Old Schema

If you have old tables (price_data, volatility_metrics, regime_classifications, composite_scores), run the migration script:

```bash
python migrate_tables.py
```

This will:
1. Create new turbulence_ prefixed tables
2. Migrate existing data
3. Drop old tables
4. Preserve your existing stock_prices table

### Fetch Specific Tickers

```python
# Fetch custom ticker list
tickers = ['SPY', 'QQQ', 'IWM']
df = fetcher.fetch_multiple_tickers(tickers, start_date='2023-01-01')

# Store in database
with db.get_connection() as conn:
    inserted, updated = fetcher.store_price_data(conn, df)
```

### Query Data

```python
with db.get_connection() as conn:
    with conn.cursor() as cur:
        # Query price data from existing stock_prices table
        cur.execute("""
            SELECT date, close
            FROM stock_prices
            WHERE ticker = 'SPY'
            AND date >= '2024-01-01'
            ORDER BY date
        """)
        results = cur.fetchall()

        # Query turbulence metrics
        cur.execute("""
            SELECT date, composite_score, regime_label
            FROM turbulence_composite_scores
            WHERE date >= '2024-01-01'
            ORDER BY date
        """)
        turbulence_results = cur.fetchall()
```

## Environment Variables

Required environment variables (stored in `.env`):

```
# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Polygon.io API (optional, falls back to yfinance)
POLYGON_API_KEY=your_api_key_here
```

## Testing

Run the test scripts to verify functionality:

```bash
# Test basic database setup
python test_database_setup.py

# Fetch all required tickers
python test_full_data_fetch.py
```

## Current Status

After migration:
- Uses existing stock_prices table (no data duplication)
- 3 turbulence-specific tables created with turbulence_ prefix
- All indexes created for optimal query performance
- Both Polygon.io and yfinance data sources operational
- Data stored in your existing database schema

## Integration with Other Modules

The database layer is designed to be used by:
- **Tier 1 Indicators** (`tier1.py`): Reads price data, writes volatility metrics
- **Tier 2 Models** (`tier2.py`): Reads price/volatility data, writes regime classifications
- **Tier 3 Turbulence** (`tier3.py`): Reads multi-asset data, writes turbulence indices
- **Composite Scoring** (`composite.py`): Reads all metrics, writes final scores
- **CLI Interface**: Provides data fetching and analysis commands

## Error Handling

The database module includes:
- Connection pooling with automatic reconnection
- Transaction rollback on errors
- Proper resource cleanup via context managers
- Logging of all database operations
- Custom exceptions for database errors

## Performance Considerations

- Indexes on (ticker, date) for fast time-series queries
- Connection pooling reduces overhead
- Batch inserts for efficiency
- Uses existing stock_prices table (no duplication, faster queries)
- Turbulence tables are smaller and optimized for regime detection queries
- Separate tables allow independent maintenance and archiving
