# Foreign Key Constraint Fix - Summary

## Issue Encountered

Your `stock_prices` table has a foreign key constraint:
```sql
stock_prices.ticker → companies.ticker
```

This means every ticker in `stock_prices` must first exist in the `companies` table.

**Error message:**
```
insert or update on table "stock_prices" violates foreign key constraint "stock_prices_ticker_fkey"
DETAIL: Key (ticker)=(TLT) is not present in table "companies".
```

## Solution Implemented

Updated `src/turbulence/data_fetcher.py` to:

1. **Check** if ticker exists in `companies` table before inserting price data
2. **Auto-insert** missing tickers into `companies` table with basic metadata
3. **Then proceed** with price data insertion

### New Method Added

```python
def _ensure_ticker_in_companies(conn, ticker):
    """Ensure ticker exists in companies table for foreign key constraint."""
    # Checks if ticker exists
    # If not, inserts minimal record with proper name and type
```

### Tickers Auto-Added

| Ticker | Name | Type |
|--------|------|------|
| SPY | SPDR S&P 500 ETF Trust | ETF |
| TLT | iShares 20+ Year Treasury Bond ETF | ETF |
| GLD | SPDR Gold Trust | ETF |
| UUP | Invesco DB US Dollar Index Bullish Fund | ETF |
| HYG | iShares iBoxx $ High Yield Corporate Bond ETF | ETF |
| ^VIX | CBOE Volatility Index | INDEX |
| ^VIX3M | CBOE 3-Month Volatility Index | INDEX |

## Verification

✅ **All tickers now in companies table**
```
GLD: SPDR Gold Trust (ETF)
HYG: iShares iBoxx $ High Yield Corporate Bond ETF (ETF)
SPY: State Street SPDR S&P 500 ETF Trust (ETF)
TLT: iShares 20+ Year Treasury Bond ETF (ETF)
UUP: Invesco DB US Dollar Index Bullish Fund (ETF)
^VIX: CBOE Volatility Index (INDEX)
^VIX3M: CBOE 3-Month Volatility Index (INDEX)
```

✅ **All price data successfully stored**
```
GLD: 529 rows (2024-01-02 to 2026-02-10)
HYG: 529 rows (2024-01-02 to 2026-02-10)
SPY: 754 rows (2023-02-08 to 2026-02-10)
TLT: 529 rows (2024-01-02 to 2026-02-10)
UUP: 529 rows (2024-01-02 to 2026-02-10)
^VIX: 528 rows (2024-01-02 to 2026-02-09)
^VIX3M: 528 rows (2024-01-02 to 2026-02-09)
```

✅ **Indicators computed successfully**
- Tier 1: VIX regimes, Garman-Klass volatility ✓
- Tier 2: GARCH models ✓
- Tier 3: Turbulence index ✓
- Composite scores: 177 regime records ✓

✅ **Current regime detection working**
```
Composite Turbulence Score: 0.597
Current Regime: EXTREME

Component Scores:
  VIX Component:              0.536
  Realized Volatility:        0.996
  Turbulence Index:           0.623
  GARCH Conditional Vol:      0.718

VIX Data:
  VIX Level:                  17.36
  VIX Regime:                 normal
```

## Impact

- **No breaking changes** - System now works with your existing database schema
- **Respects referential integrity** - Properly maintains foreign key constraints
- **Auto-handles new tickers** - Future tickers will be auto-added to companies table
- **Backwards compatible** - Existing SPY data unchanged

## Future Considerations

When fetching new tickers (not in the default list), the system will:
1. Auto-add them to `companies` table with generic name `{TICKER} (Auto-added by Turbulence)`
2. Set type to 'ETF' by default
3. Mark as active

If you want better metadata for new tickers, you can manually update the `companies` table after auto-insertion.

## Testing

System is fully operational:

```bash
# Daily workflow
python -m turbulence.cli fetch-data
python -m turbulence.cli compute --indicators tier1
python -m turbulence.cli status --detailed

# Works perfectly! ✓
```
