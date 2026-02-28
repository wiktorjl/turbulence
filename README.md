# Turbulence - Market Regime Detection System

A CLI tool for detecting financial market turbulence using multi-tier statistical models and cross-asset analysis. Combines VIX indicators, HMM, GARCH, and Mahalanobis-distance turbulence indices to classify market regimes (low/normal/elevated/extreme) and inform position sizing, stop widths, and strategy selection for ES futures and options trading.

## Prerequisites

- Python 3.8+
- PostgreSQL (with an existing `stock_prices` table, or use `turbulence init-db` to create the schema)
- Polygon.io API key (optional; falls back to yfinance for free data)

## Quick Start

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Install in development mode
pip install -e .

# 3. Initialize database
turbulence init-db

# 4. Fetch historical data (5 years, default tickers)
turbulence fetch-data

# 5. Compute turbulence indicators
turbulence compute

# 6. Check current market regime
turbulence status --detailed
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

Maps to four regimes using fixed thresholds with a 3-day persistence filter:
- **Low** (0.00-0.25): Calm markets, normal trading
- **Normal** (0.25-0.50): Average volatility
- **Elevated** (0.50-0.75): Heightened uncertainty, reduce risk
- **Extreme** (0.75-1.00): Crisis conditions, defensive positioning

## CLI Commands

### Initialize Database

```bash
turbulence init-db
```

Creates PostgreSQL tables for volatility metrics, regime classifications, and composite scores.

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
```

### Run Backtest

Walk-forward validation that slides a training window through historical data,
running the full tier1-tier2-tier3-composite pipeline on each window and evaluating
out-of-sample predictions.

```bash
# Standard 3-year train / 6-month test backtest
turbulence backtest --start-date 2015-01-01 --end-date 2023-12-31

# Custom walk-forward parameters
turbulence backtest --start-date 2015-01-01 --train-window 500 --test-window 100 --step-size 63

# Save results to CSV
turbulence backtest --start-date 2015-01-01 --output backtest_results.csv
```

### Generate Report

Generates a self-contained HTML report with regime timeline, component analysis,
and trading recommendations.

```bash
# Generate HTML report for last year
turbulence report --output turbulence_report.html

# Generate report for custom period
turbulence report --start-date 2020-01-01 --end-date 2023-12-31 --output report.html

# Generate report without charts (faster)
turbulence report --output report.html --no-include-charts
```

Note: PDF output requires the `weasyprint` package (`pip install weasyprint`).

### Generate Chart

```bash
# Generate turbulence chart (requires matplotlib)
turbulence chart --output chart.png

# YTD chart
turbulence chart --ytd --output ytd.png
```

## Configuration

Configuration is managed via `.env` file at the project root:

```bash
# PostgreSQL connection (required)
DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres

# Polygon.io API key (optional; falls back to yfinance)
POLYGON_API_KEY=your_api_key

# Optional settings
LOG_LEVEL=INFO
DB_POOL_MIN=1
DB_POOL_MAX=10
API_RATE_LIMIT_DELAY=0.2
API_MAX_RETRIES=3
```

## Database Schema

### stock_prices (existing table, not modified)
- ticker, date, open, high, low, close, volume

### turbulence_volatility_metrics
- ticker, date, garman_klass_vol, parkinson_vol, rogers_satchell_vol, etc.

### turbulence_regime_classifications
- date, vix_level, vix_regime, turbulence_index, hmm_state, absorption_ratio, etc.

### turbulence_composite_scores
- date, vix_component, turbulence_component, composite_score, regime_label

## Trading Applications

### ES Futures
- **Position sizing**: Cut risk 25-50% when turbulence > 0.50, half size when > 0.75
- **Stop widths**: Widen S/R zones by 1.5x ATR in high-vol regimes
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
├── composite.py         # Composite scoring with persistence filter
├── backtest.py          # Walk-forward validation engine
├── report.py            # HTML report generator
└── utils.py             # Error handling and utilities
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Code formatting
black src/

# Type checking
mypy src/
```

## Key References

- Kritzman & Li (2010): "Skulls, Financial Turbulence, and Risk Management"
- Hamilton (1989): Regime-switching framework
- Ang & Bekaert (2002, 2004): Regime-based asset allocation
- Kritzman et al. (2011): Absorption ratio for systemic risk

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

See [TURBULENCE.md](docs/TURBULENCE.md) for the full design document and academic references.
