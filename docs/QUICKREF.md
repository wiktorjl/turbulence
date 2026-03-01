# Turbulence System - Quick Reference Card

## One-Line Summary
Market regime detector that tells you when to reduce risk in ES futures/options trading.

## Current Status
✅ **Working!** Regime: EXTREME (0.597) - Reduce position sizes, widen stops

## Daily Commands

```bash
# Morning routine (3 commands - takes ~1-2 minutes total)
source .venv/bin/activate
python -m turbulence.cli fetch-data           # Fetch latest prices
python -m turbulence.cli compute              # Compute ALL indicators
python -m turbulence.cli status --detailed    # Check regime

# IMPORTANT: Don't use --indicators tier1 for daily workflow
# The composite score needs all tiers (tier1, tier2, tier3)
```

## What Each Regime Means

| Score | Regime | ES Futures | Options |
|-------|--------|------------|---------|
| 0-25% | **Low** | Normal trading | Buy cheap puts |
| 25-50% | **Normal** | Standard approach | Balanced strategies |
| 50-75% | **Elevated** | Cut size 25-50%, widen stops | Sell premium |
| 75-100% | **Extreme** | Half size or stand aside | Defined risk only |

## Essential Commands

```bash
# Check regime
python -m turbulence.cli status --detailed

# Fetch missing tickers (one-time)
python -m turbulence.cli fetch-data --start-date 2020-01-01

# Recompute (fast)
python -m turbulence.cli compute

# Retrain models (weekly)
python -m turbulence.cli compute --retrain
```

## Data Storage

All data stored as **parquet files** in `~/.turbulence/data/` (configurable via `TURBULENCE_DATA_DIR` env var):
- `prices/` — OHLCV price data per ticker
- `composite_scores.parquet` — Final turbulence score (0-1)
- `regime_classifications.parquet` — VIX regimes, HMM states

## Key Files

- **[USAGE.md](USAGE.md)** ← **START HERE** - Complete guide
- [CLAUDE.md](../CLAUDE.md) - Technical architecture
- [TURBULENCE.md](TURBULENCE.md) - Design document

## Need Help?

1. Check [USAGE.md](USAGE.md) - Has everything
2. Run `python -m turbulence.cli COMMAND --help`
3. Check logs (if errors occur)

## Pro Tips

- Retrain models monthly for best accuracy
- Combine with your own S/R analysis
- Trust low/extreme regimes more than borderline cases
- Use filtered probabilities, not hard regime switches
