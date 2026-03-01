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
turbulence init
turbulence fetch-data
turbulence compute
turbulence status --detailed

# Alternative: run without installing
python -m turbulence.cli --help

# Run tests
pytest tests/ -v

# Formatting and linting
black src/
flake8 src/
mypy src/

# Generate turbulence chart
turbulence chart --ytd --output chart.png
```

## Architecture

### Source Layout (`src/turbulence/`)

The package uses a `src` layout with setuptools. Entry point: `turbulence.cli:main` (Click CLI).

**Data flow:** `data_fetcher.py` → parquet files → `cli.py compute` reads from parquet → runs `tier1` → `tier2` → `tier3` → `composite.py` → writes results back to parquet.

**Storage:** All data stored as parquet files in `~/.turbulence/data/` (configurable via `TURBULENCE_DATA_DIR` env var). See `storage.py`.

- **`config.py`** — Singleton `Config` class loading from `.env` via `python-dotenv`. Optional env var: `TURBULENCE_DATA_DIR`.
- **`storage.py`** — Parquet-based file storage. Functions: `save_prices()`, `load_prices()`, `load_all_prices()`, `save_composite_scores()`, `load_composite_scores()`, `save_regime_classifications()`, `load_regime_classifications()`. Upsert semantics on save.
- **`data_fetcher.py`** — `DataFetcher` uses yfinance for all data fetching. Stores to parquet via `storage.save_prices()`.
- **`tier1.py`** — VIX regime classification (5 levels), VIX/VIX3M term structure ratio, Garman-Klass volatility (30-day rolling window, annualized), percentile-based classification (252-day rolling window).
- **`tier2.py`** — Gaussian HMM (hmmlearn), GJR-GARCH(1,1) (arch library, scales returns to % for numerical stability), Hamilton regime-switching (statsmodels MarkovRegression). All have rolling-window variants.
- **`tier3.py`** — `KritzmanLiTurbulence` (Mahalanobis distance with Ledoit-Wolf shrinkage), `AbsorptionRatio` (PCA on 500-day window), `RegimeClustering` (GMM with 5 rolling features).
- **`composite.py`** — `CompositeScorer` combines 5 normalized components with configurable weights using simple fixed thresholds (0.25, 0.50, 0.75) and 3-day persistence filter to prevent whipsaw.
- **`utils.py`** — Custom exceptions (`DatabaseConnectionError`, `APIRateLimitError`, `MissingDataError`, `NumericalInstabilityError`), retry/rate-limit decorators, covariance matrix regularization.

## Configuration

Optional `.env` file at project root:
```
TURBULENCE_DATA_DIR=~/.turbulence/data   # optional, this is the default
LOG_LEVEL=INFO
API_RATE_LIMIT_DELAY=0.2
API_MAX_RETRIES=3
```

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
