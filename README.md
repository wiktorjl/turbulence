# Turbulence - Market Regime Detection System

A comprehensive CLI tool for detecting financial market turbulence using multi-tier statistical models and cross-asset analysis.

**📖 Quick Start:** See [USAGE.md](USAGE.md) for complete executive summary and usage guide.

## Quick Start

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Migrate to new schema (one-time, if upgrading from old version)
python migrate_tables.py

# 3. Initialize database
python -m turbulence.cli init-db

# 4. Fetch historical data (5 years, default tickers)
python -m turbulence.cli fetch-data

# 5. Compute turbulence indicators
python -m turbulence.cli compute

# 6. Check current market regime
python -m turbulence.cli status --detailed
```

## Overview

The Turbulence system combines VIX indicators, statistical models (HMM, GARCH), and multi-asset turbulence indices to classify market regimes and provide actionable trading insights for ES futures and options traders.

**New:** Now uses your existing `stock_prices` table and adds only 3 turbulence-specific tables with `turbulence_` prefix.

## Installation

```bash
# Activate virtual environment
source .venv/bin/activate

# Install in development mode
pip install -e .
```

## Architecture

### Tier 1: Fast Indicators
- **VIX regime classification**: Threshold-based (VIX < 15 = complacent, 15-20 = normal, 20-25 = elevated, 25-30 = high, > 30 = panic)
- **VIX term structure**: VIX/VIX3M ratio detecting backwardation (stress) vs contango (calm)
- **Garman-Klass volatility**: OHLC-based estimator on rolling 30-day windows, annualized
- **Percentile classification**: Auto-adapting quartile-based regime detection

### Tier 2: Statistical Models
- **Hidden Markov Models**: 2-3 state Gaussian HMM using filtered probabilities (not Viterbi)
- **GJR-GARCH(1,1)**: Asymmetric volatility with Student's t distribution
- **Hamilton regime-switching**: Markov regression with switching variance

### Tier 3: Multi-Asset Turbulence
- **Kritzman & Li turbulence index**: Mahalanobis distance detecting correlation breakdowns
- **Absorption ratio**: PCA-based systemic fragility measure
- **Gaussian Mixture Models**: Unsupervised regime clustering

### Composite Scoring
Combines five normalized (0-1) components with weights:
- VIX percentile (25%)
- VIX term structure (15%)
- Realized vol percentile (20%)
- Turbulence index percentile (25%)
- GARCH conditional vol percentile (15%)

Maps to four regimes:
- **Low** (0.00-0.25): Calm markets, normal trading
- **Normal** (0.25-0.50): Average volatility
- **Elevated** (0.50-0.75): Heightened uncertainty, reduce risk
- **Extreme** (0.75-1.00): Crisis conditions, defensive positioning

## CLI Commands

### Initialize Database

```bash
turbulence init-db
```

Creates PostgreSQL tables for price data, volatility metrics, regime classifications, and composite scores.

### Fetch Market Data

```bash
# Fetch default tickers (SPY, TLT, GLD, UUP, HYG, ^VIX, ^VIX3M) for last 5 years
turbulence fetch-data

# Fetch specific date range and tickers
turbulence fetch-data --start-date 2020-01-01 --end-date 2023-12-31 --tickers SPY,VIX

# Initialize DB and fetch data in one command
turbulence fetch-data --init-db
```

### Compute Indicators

```bash
# Compute all indicators (Tier 1, 2, 3, composite)
turbulence compute

# Compute specific tier
turbulence compute --indicators tier1

# Retrain statistical models
turbulence compute --retrain

# Compute for specific date range
turbulence compute --start-date 2024-01-01
```

### Check Current Status

```bash
# Show current market regime
turbulence status

# Show detailed component scores
turbulence status --detailed

# Export status as JSON
turbulence status --format json

# Check status for specific date
turbulence status --date 2024-03-15
```

### Run Backtest

```bash
# Standard 3-year train / 6-month test backtest
turbulence backtest --start-date 2015-01-01 --end-date 2023-12-31

# Custom walk-forward parameters
turbulence backtest --start-date 2015-01-01 --train-window 500 --test-window 100 --step-size 63

# Save results to CSV
turbulence backtest --start-date 2015-01-01 --output backtest_results.csv
```

### Generate Report

```bash
# Generate HTML report for last year
turbulence report --output turbulence_report.html

# Generate PDF report for custom period
turbulence report --start-date 2020-01-01 --end-date 2023-12-31 --output report.pdf --format pdf
```

## Configuration

Configuration is managed via `.env` file:

```bash
# PostgreSQL connection
DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres

# Polygon.io API credentials
POLYGON_API_KEY=your_api_key
POLYGON_S3_ACCESS_KEY=your_s3_key
POLYGON_S3_SECRET_KEY=your_s3_secret

# Optional settings
LOG_LEVEL=INFO
DB_POOL_MIN=1
DB_POOL_MAX=10
API_RATE_LIMIT_DELAY=0.2
API_MAX_RETRIES=3
```

## Database Schema

### stock_prices (Existing - Not Modified)
- ticker, date, open, high, low, close, volume
- Your existing table for OHLCV data

### turbulence_volatility_metrics (New)
- ticker, date, garman_klass_vol, parkinson_vol, rogers_satchell_vol, etc.
- Stores calculated volatility metrics

### turbulence_regime_classifications (New)
- date, vix_level, vix_regime, turbulence_index, hmm_state, absorption_ratio, etc.
- Stores regime indicators and model outputs

### turbulence_composite_scores (New)
- date, vix_component, turbulence_component, composite_score, regime_label
- Stores final composite scores and regime classifications

## Trading Applications

### ES Futures
- **Position sizing**: Cut risk 25-50% when turbulence > 0.50, half size when > 0.75
- **Stop widths**: Widen S/R zones by 1.5× ATR in high-vol regimes
- **Strategy selection**: S/R bounces in low-vol, momentum/breakout in high-vol

### Options
- **Low-vol regimes**: Buy cheap OTM puts, consider debit spreads
- **High-vol regimes**: Sell premium via credit spreads (90% of VIX > 30 spikes resolve in 3 months)
- **Extreme regimes**: Avoid naked short premium, use defined-risk spreads

## Module Structure

```
src/turbulence/
├── __init__.py          # Package initialization and exports
├── cli.py               # Click-based CLI interface
├── config.py            # Configuration management
├── database.py          # PostgreSQL schema and connection pooling
├── data_fetcher.py      # Polygon.io + yfinance data fetching
├── tier1.py             # VIX and Garman-Klass indicators
├── tier2.py             # HMM, GARCH, Hamilton models
├── tier3.py             # Turbulence index, Absorption Ratio, GMM
├── composite.py         # Composite scoring with hysteresis
└── utils.py             # Error handling and utilities
```

## Data Sources

- **yfinance**: Free daily data for equities, ETFs, VIX indices
- **Polygon.io**: Premium market data with API credentials (configured in .env)
- **FRED API**: Credit spreads, yield curves (optional, via fredapi library)

## Key References

- Kritzman & Li (2010): "Skulls, Financial Turbulence, and Risk Management"
- Hamilton (1989): Regime-switching framework
- Ang & Bekaert (2002, 2004): Regime-based asset allocation
- Kritzman et al. (2011): Absorption ratio for systemic risk

## Development

```bash
# Run tests
pytest tests/

# Code formatting
black src/

# Type checking
mypy src/
```

## License

See TURBULENCE.md for the full design document and academic references.
