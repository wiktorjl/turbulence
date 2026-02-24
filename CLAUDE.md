# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Market turbulence regime detection system for ES futures and options trading. Combines VIX indicators, statistical models (HMM, GARCH), and cross-asset turbulence indices to classify market regimes (low/normal/elevated/extreme) and inform position sizing, stop widths, and strategy selection.

The full design document lives in `docs/TURBULENCE.md`.

## Development Commands

```bash
# Activate virtual environment
source .venv/bin/activate

# Install in development mode (src layout)
pip install -e .

# Install dev dependencies
pip install -e ".[dev]"

# Run the CLI (after install)
turbulence --help
turbulence init-db
turbulence fetch-data
turbulence compute
turbulence status --detailed

# Alternative: run without installing
python -m turbulence.cli --help

# Run tests (test files are at repo root, not in tests/ dir)
python test_database_setup.py
python test_full_data_fetch.py

# Formatting and linting
black src/
flake8 src/
mypy src/

# Generate turbulence chart
python plot_turbulence.py --start-date 2024-01-01 --output chart.png
```

## Architecture

### Source Layout (`src/turbulence/`)

The package uses a `src` layout with setuptools. Entry point: `turbulence.cli:main` (Click CLI).

**Data flow:** `data_fetcher.py` → PostgreSQL → `cli.py compute` reads from DB → runs `tier1` → `tier2` → `tier3` → `composite.py` → writes results back to DB.

- **`config.py`** — Singleton `Config` class loading from `.env` via `python-dotenv`. Required env vars: `DATABASE_URL`, `POLYGON_API_KEY`.
- **`database.py`** — `DatabaseManager` with psycopg2 connection pooling. Creates 3 turbulence-specific tables (`turbulence_volatility_metrics`, `turbulence_regime_classifications`, `turbulence_composite_scores`). Relies on pre-existing `stock_prices` and `companies` tables.
- **`data_fetcher.py`** — `DataFetcher` tries Polygon.io first, falls back to yfinance. Handles yfinance's exclusive end date by adding +1 day. Ensures tickers exist in `companies` table before inserting prices.
- **`tier1.py`** — VIX regime classification (5 levels), VIX/VIX3M term structure ratio, Garman-Klass volatility (30-day rolling window, annualized), percentile-based classification (252-day rolling window).
- **`tier2.py`** — Gaussian HMM (hmmlearn), GJR-GARCH(1,1) (arch library, scales returns to % for numerical stability), Hamilton regime-switching (statsmodels MarkovRegression). All have rolling-window variants.
- **`tier3.py`** — `KritzmanLiTurbulence` (Mahalanobis distance with Ledoit-Wolf shrinkage), `AbsorptionRatio` (PCA on 500-day window), `RegimeClustering` (GMM with 5 rolling features).
- **`composite.py`** — `CompositeScorer` combines 5 normalized components with configurable weights using simple fixed thresholds (0.25, 0.50, 0.75) and 3-day persistence filter to prevent whipsaw.
- **`utils.py`** — Custom exceptions (`DatabaseConnectionError`, `APIRateLimitError`, `MissingDataError`, `NumericalInstabilityError`), retry/rate-limit decorators, covariance matrix regularization.

### Unimplemented Features

The `backtest` and `report` CLI commands are stubs with placeholder logic (marked with TODO comments in `cli.py`). The `chart` command delegates to `plot_turbulence.py`.

## Configuration

Requires a `.env` file at project root:
```
DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres
POLYGON_API_KEY=your_key
```
Optional: `LOG_LEVEL`, `DB_POOL_MIN`, `DB_POOL_MAX`, `API_RATE_LIMIT_DELAY`, `API_MAX_RETRIES`, `POLYGON_S3_ACCESS_KEY`, `POLYGON_S3_SECRET_KEY`.

## Critical Implementation Guidelines

### Avoiding Look-Ahead Bias
- **Never use full-sample statistics**: Always use rolling windows for means, covariances
- **HMM inference**: Use filtered probabilities (forward algorithm) NOT Viterbi decoding
- **Walk-forward validation**: Train on 3-4 year window, test on next 6-12 months, slide forward
- **Rolling windows**: 252 days for annual stats, 30 days for short-term vol, 500 days for absorption ratio

### Whipsaw Prevention
- **Simple thresholds**: Fixed regime boundaries at 0.25, 0.50, 0.75 (defined in `composite.py` `REGIME_THRESHOLDS`)
- **Persistence filter**: Requires regime to hold for 3 consecutive days before confirming transition
- **Probabilistic sizing**: For trading, prefer using HMM filtered probabilities directly rather than hard regime labels

### Model Selection
- Compare models using BIC
- HMM: Sort states by covariance determinant to label low vs high vol
- GARCH: GJR-GARCH with Student's t; scale returns to percentage for numerical stability (see `tier2.py:131`)
- Tier 3 turbulence: Uses Ledoit-Wolf shrinkage for stable covariance estimation

### Backtest Red Flags
Returns > 12% annual, Sharpe > 1.5, suspiciously smooth equity curves
