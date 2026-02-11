# Migration Summary - Turbulence System Refactoring

## Changes Made

### 1. Database Schema Changes

**Before:**
- Created separate `price_data` table (duplicating your existing data)
- Tables: `price_data`, `volatility_metrics`, `regime_classifications`, `composite_scores`

**After:**
- Uses your existing `stock_prices` table (no duplication)
- New turbulence-specific tables with `turbulence_` prefix:
  - `turbulence_volatility_metrics`
  - `turbulence_regime_classifications`
  - `turbulence_composite_scores`

### 2. Code Changes

**Files Modified:**
- `src/turbulence/database.py` - Updated to create turbulence_ tables, uses stock_prices
- `src/turbulence/data_fetcher.py` - Stores data in stock_prices instead of price_data
- `src/turbulence/cli.py` - Updated all table references to new names

**Files Created:**
- `USAGE.md` - Comprehensive usage guide with examples
- `migrate_tables.py` - Migration script to move from old schema to new
- `MIGRATION_SUMMARY.md` - This file

**Files Updated:**
- `README.md` - Added quick start section
- `DATABASE_README.md` - Updated to reflect new schema

### 3. CLI Improvements

The CLI already has good one-shot options. All commands support:

```bash
# Fetch data with custom parameters
python -m turbulence.cli fetch-data \
  --start-date 2020-01-01 \
  --end-date 2024-12-31 \
  --tickers SPY,QQQ,^VIX

# Compute specific tier
python -m turbulence.cli compute \
  --indicators tier1 \
  --start-date 2024-01-01 \
  --retrain

# Check status with options
python -m turbulence.cli status \
  --date 2024-03-15 \
  --detailed \
  --format json

# Backtest with custom parameters
python -m turbulence.cli backtest \
  --start-date 2015-01-01 \
  --train-window 756 \
  --test-window 126 \
  --output results.csv

# Generate report
python -m turbulence.cli report \
  --start-date 2020-01-01 \
  --output report.html \
  --format html
```

No interactive prompts - all parameters can be specified via command-line flags.

## Migration Steps

### Step 1: Run Migration Script

```bash
# Activate virtual environment
source .venv/bin/activate

# Run migration (will prompt for confirmation)
python migrate_tables.py
```

This will:
1. Create new `turbulence_*` tables
2. Copy data from old tables to new ones
3. Drop old tables (`price_data`, `volatility_metrics`, etc.)
4. Preserve your existing `stock_prices` table

### Step 2: Verify Migration

```bash
# Check database tables
python -c "
import psycopg2
conn = psycopg2.connect('postgresql://postgres:Hello7710@localhost:5432/postgres')
cur = conn.cursor()
cur.execute(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'turbulence_%' ORDER BY table_name\")
print('Turbulence tables:')
for row in cur.fetchall():
    print(f'  - {row[0]}')
cur.close()
conn.close()
"
```

Expected output:
```
Turbulence tables:
  - turbulence_composite_scores
  - turbulence_regime_classifications
  - turbulence_volatility_metrics
```

### Step 3: Test the System

```bash
# Check current status
python -m turbulence.cli status --detailed

# Fetch latest data
python -m turbulence.cli fetch-data --start-date 2024-01-01

# Recompute indicators
python -m turbulence.cli compute
```

## What Didn't Change

- Your existing `stock_prices` table is **untouched**
- All other existing tables (balance_sheets, cash_flows, companies, etc.) are **untouched**
- The turbulence system only adds 3 new tables with the `turbulence_` prefix
- All configuration in `.env` remains the same
- Virtual environment and dependencies remain the same

## Benefits of New Schema

1. **No data duplication** - Uses your existing stock_prices table
2. **Clear namespace** - turbulence_ prefix prevents conflicts
3. **Better organization** - Turbulence tables are separate from general market data
4. **Easier maintenance** - Can drop/recreate turbulence tables without affecting price data
5. **Smaller footprint** - No duplicate OHLCV data taking up disk space

## Rollback (If Needed)

If you need to rollback:

```sql
-- Rename old tables back if they still exist
-- (Migration script drops them, so this only works if you didn't run it)
DROP TABLE IF EXISTS turbulence_composite_scores CASCADE;
DROP TABLE IF EXISTS turbulence_regime_classifications CASCADE;
DROP TABLE IF EXISTS turbulence_volatility_metrics CASCADE;

-- Recreate old schema
-- (Use old version of database.py if needed)
```

## Questions?

- **Usage:** See [USAGE.md](USAGE.md)
- **Technical details:** See [CLAUDE.md](CLAUDE.md) and [TURBULENCE.md](TURBULENCE.md)
- **Database schema:** See [DATABASE_README.md](DATABASE_README.md)
