# Turbulence Tier System - Complete Guide

## Understanding the Three Tiers

The turbulence system computes indicators in three tiers of increasing sophistication:

### Tier 1: Fast Indicators (~5 seconds)

**What it computes:**
- VIX regime classification (complacent, normal, elevated, high, panic)
- VIX term structure ratio (VIX/VIX3M)
- Garman-Klass realized volatility (OHLC-based)
- Volatility percentiles (rolling 252-day windows)

**Speed:** Very fast (< 5 seconds)
**Data required:** SPY OHLC, VIX, VIX3M
**Output:** Basic volatility metrics, VIX regime

### Tier 2: Statistical Models (~10-20 seconds)

**What it computes:**
- GJR-GARCH(1,1) conditional volatility forecasts
- Hidden Markov Models (2-3 state Gaussian HMM)
- Hamilton regime-switching models

**Speed:** Moderate (10-20 seconds without retraining)
**Data required:** SPY returns (252+ days)
**Output:** GARCH volatility forecasts, HMM state probabilities

### Tier 3: Multi-Asset Turbulence (~10-15 seconds)

**What it computes:**
- Kritzman & Li turbulence index (Mahalanobis distance)
- Absorption ratio (PCA-based systemic risk)
- Gaussian Mixture Models (optional)

**Speed:** Moderate (10-15 seconds)
**Data required:** SPY, TLT, GLD, UUP, HYG returns (252+ days)
**Output:** Cross-asset turbulence index, absorption ratio

### Composite Scoring (~1 second)

**What it computes:**
- Weighted average of all 5 components:
  - VIX percentile (25% weight) ← Tier 1
  - VIX term structure (15% weight) ← Tier 1
  - Realized vol percentile (20% weight) ← Tier 1
  - Turbulence index percentile (25% weight) ← Tier 3
  - GARCH conditional vol percentile (15% weight) ← Tier 2

**Speed:** Instant
**Data required:** All tier outputs
**Output:** Final composite score (0-1), regime label

## Command Options

### `turbulence compute` (Default - RECOMMENDED)

```bash
turbulence compute
```

**Computes:** All tiers + composite score
**Time:** ~30-60 seconds
**Use case:** Daily routine, full update
**Updates:** Everything including composite score ✅

### `turbulence compute --indicators all` (Explicit)

```bash
turbulence compute --indicators all
```

**Same as default** - explicitly states to compute all indicators.

### `turbulence compute --indicators tier1`

```bash
turbulence compute --indicators tier1
```

**Computes:** Only VIX regime and realized volatility
**Time:** < 5 seconds
**Use case:** Quick VIX check only
**⚠️ WARNING:** Does NOT update composite score!

**Problem:**
- Composite score becomes stale
- `status` command shows old score
- Misleading for trading decisions
- Missing 60% of score (GARCH + turbulence)

**When to use:** Almost never! Only for debugging/testing.

### `turbulence compute --indicators tier2`

```bash
turbulence compute --indicators tier2
```

**Computes:** Only GARCH models
**Time:** ~10-20 seconds
**Use case:** Testing GARCH only
**⚠️ WARNING:** Does NOT update composite score!

### `turbulence compute --indicators tier3`

```bash
turbulence compute --indicators tier3
```

**Computes:** Only turbulence index
**Time:** ~10-15 seconds
**Use case:** Testing turbulence only
**⚠️ WARNING:** Does NOT update composite score!

### `turbulence compute --retrain`

```bash
turbulence compute --retrain
```

**Computes:** All tiers + retrains models from scratch
**Time:** 2-5 minutes
**Use case:** Weekly/monthly model updates
**Updates:** Everything + fresh model parameters ✅

**When to use:**
- First of month (monthly retraining)
- After major market events
- When model parameters seem stale
- After adding significant historical data

## Decision Matrix

| Scenario | Command | Time | Composite Updated? |
|----------|---------|------|-------------------|
| **Daily pre-market** | `turbulence compute` | 30-60s | ✅ YES |
| **Weekly analysis** | `turbulence compute --retrain` | 2-5m | ✅ YES |
| **Monthly maintenance** | `turbulence compute --retrain --indicators all` | 2-5m | ✅ YES |
| **Quick VIX check** | `turbulence compute --indicators tier1` | <5s | ❌ NO (stale!) |
| **Testing GARCH only** | `turbulence compute --indicators tier2` | 10-20s | ❌ NO (stale!) |
| **Testing turbulence only** | `turbulence compute --indicators tier3` | 10-15s | ❌ NO (stale!) |

## Why You Need All Tiers Daily

### Component Weights in Composite Score

```
Composite Score = 0.25×VIX_pct + 0.15×VIX_term + 0.20×RealVol_pct
                  + 0.25×Turb_idx + 0.15×GARCH_pct

Tier 1 provides: 60% of score (VIX_pct + VIX_term + RealVol_pct)
Tier 2 provides: 15% of score (GARCH_pct)
Tier 3 provides: 25% of score (Turb_idx)
```

**If you skip tier 2 + tier 3:**
- Missing 40% of the composite score
- GARCH and turbulence components use old data
- Score doesn't reflect current market conditions
- Trading decisions based on stale information

### Example: What Goes Wrong

**Scenario:** VIX spikes from 15 to 25 overnight

```bash
# WRONG: Only compute tier1
turbulence compute --indicators tier1

Result:
  VIX_pct: 0.85 (updated ✅)
  VIX_term: 0.75 (updated ✅)
  RealVol_pct: 0.80 (updated ✅)
  Turb_idx: 0.20 (STALE from 3 days ago ❌)
  GARCH_pct: 0.30 (STALE from 3 days ago ❌)

  Composite: 0.25×0.85 + 0.15×0.75 + 0.20×0.80 + 0.25×0.20 + 0.15×0.30
           = 0.2125 + 0.1125 + 0.16 + 0.05 + 0.045
           = 0.58 (ELEVATED)

  But reality: Turbulence index probably spiked to 0.70
               GARCH vol probably jumped to 0.65
               True score: ~0.72 (EXTREME!)

Trading decision: Reduce to 50% size (elevated)
Correct decision: Stand aside (extreme)

Result: You take a trade you shouldn't, get stopped out
```

**Correct approach:**

```bash
# RIGHT: Compute all indicators
turbulence compute

Result:
  VIX_pct: 0.85 (updated ✅)
  VIX_term: 0.75 (updated ✅)
  RealVol_pct: 0.80 (updated ✅)
  Turb_idx: 0.70 (updated ✅)
  GARCH_pct: 0.65 (updated ✅)

  Composite: 0.72 (EXTREME)

Trading decision: Stand aside
Result: Avoid whipsaw, preserve capital ✅
```

## Recommended Workflows

### Daily Pre-Market (STANDARD)

```bash
source .venv/bin/activate
turbulence fetch-data
turbulence compute              # ← All tiers
turbulence status --detailed
turbulence chart --last-3m
```

**Time:** ~2 minutes total
**Frequency:** Every trading day
**Purpose:** Full daily update

### Weekly Analysis (FULL RETRAIN)

```bash
turbulence fetch-data --start-date 2020-01-01
turbulence compute --retrain    # ← Retrain models
turbulence status --detailed
turbulence chart --ytd
```

**Time:** ~5 minutes total
**Frequency:** Weekly (Friday evening or Sunday)
**Purpose:** Model maintenance, verify parameters

### Monthly Review (COMPREHENSIVE)

```bash
# Full refresh
turbulence fetch-data --start-date 2020-01-01

# Retrain everything from scratch
turbulence compute --retrain --indicators all

# Check current regime
turbulence status --detailed

# Generate historical chart
turbulence chart --start-date $(date -d "1 year ago" +%Y-%m-%d)
```

**Time:** ~5 minutes total
**Frequency:** Monthly (first Sunday of month)
**Purpose:** Deep validation, parameter health check

### Emergency: Fast Status Check

```bash
# If you're in a rush and just need to see the regime
turbulence status --detailed

# NOTE: This shows data from last full compute
# If you haven't run 'turbulence compute' today, this is STALE!
```

**Time:** Instant
**Frequency:** Anytime
**Purpose:** Quick check without recomputing
**⚠️ WARNING:** Shows old data if you haven't run compute today!

## Performance Notes

**Typical timing on modern hardware:**

| Command | First Run | Subsequent Runs |
|---------|-----------|-----------------|
| `turbulence fetch-data` | 10-15s | 5-10s |
| `turbulence compute` (all) | 45-60s | 30-45s |
| `turbulence compute --retrain` | 3-5m | 2-3m |
| `turbulence status` | Instant | Instant |
| `turbulence chart` | 2-3s | 2-3s |

**Bottlenecks:**
- Model fitting (GARCH, HMM) takes longest
- Turbulence index requires matrix inversion (252×252)
- First run slower due to cold cache

**Optimization tips:**
- Don't retrain daily (models are stable)
- Cache frequently accessed data
- Run compute in background while reviewing charts

## Bottom Line

**For trading decisions, ALWAYS use:**

```bash
turbulence compute  # No flags = all indicators
```

**Never use tier1-only for trading:**

```bash
turbulence compute --indicators tier1  # ❌ BAD: Stale composite score
```

**The composite score is what matters, and it needs all three tiers.**
