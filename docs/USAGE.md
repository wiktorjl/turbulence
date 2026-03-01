# Turbulence System - Executive Summary & Usage Guide

## What Is This?

A **market regime detection system** that tells you when to reduce risk, widen stops, or avoid trading ES futures/options entirely. It combines VIX levels, volatility measurements, and statistical models to classify market conditions into four regimes:

- **Low turbulence (0-25%)**: Calm markets, normal trading
- **Normal turbulence (25-50%)**: Average volatility, proceed as usual
- **Elevated turbulence (50-75%)**: Reduce position sizes, widen stops
- **Extreme turbulence (75-100%)**: Crisis mode, defensive positioning only

## Quick Start

### 1. One-Time Setup

Initialize the database schema (creates 3 turbulence-specific tables):

```bash
# Activate virtual environment
source .venv/bin/activate

# Initialize database (safe to run multiple times)
python -m turbulence.cli init-db
```

This creates:
- `turbulence_volatility_metrics` - Garman-Klass, Parkinson, Rogers-Satchell volatility
- `turbulence_regime_classifications` - VIX regimes, HMM states, turbulence index
- `turbulence_composite_scores` - Final composite turbulence score (0-1 scale)

**Note:** Price data is stored in your existing `stock_prices` table (no duplication).

### 2. Fetch Historical Data

Get 5 years of data for the default tickers (SPY, TLT, GLD, UUP, HYG, ^VIX, ^VIX3M):

```bash
# Fetch last 5 years (default)
python -m turbulence.cli fetch-data

# Custom date range
python -m turbulence.cli fetch-data --start-date 2020-01-01 --end-date 2024-12-31

# Custom tickers
python -m turbulence.cli fetch-data --tickers SPY,QQQ,^VIX
```

Data is fetched from Yahoo Finance and stored as parquet files in `~/.turbulence/data/`.

### 3. Compute Turbulence Indicators

Calculate all indicators and regime classifications:

```bash
# Compute all tiers (Tier 1: VIX, Tier 2: GARCH/HMM, Tier 3: Turbulence Index)
python -m turbulence.cli compute

# Compute only specific tier
python -m turbulence.cli compute --indicators tier1

# Compute for specific date range
python -m turbulence.cli compute --start-date 2024-01-01

# Retrain statistical models first (monthly recommended)
python -m turbulence.cli compute --retrain
```

This generates:
- VIX regime classifications (complacent, normal, elevated, high, panic)
- Garman-Klass realized volatility (8x more efficient than close-to-close)
- GARCH(1,1) conditional volatility forecasts
- Kritzman & Li turbulence index (Mahalanobis distance)
- Composite turbulence score (weighted average of 5 components)

### 4. Check Current Regime

```bash
# Show current market regime
python -m turbulence.cli status

# Show detailed component breakdown
python -m turbulence.cli status --detailed

# Export as JSON
python -m turbulence.cli status --format json

# Check specific historical date
python -m turbulence.cli status --date 2024-03-15 --detailed
```

### 5. Generate Turbulence Charts

```bash
# Year-to-date chart
python -m turbulence.cli chart --ytd

# Last 3 months chart
python -m turbulence.cli chart --last-3m

# Last 6 months chart
python -m turbulence.cli chart --last-6m

# Custom date range
python -m turbulence.cli chart --start-date 2024-01-01 --end-date 2024-12-31

# Save to specific file
python -m turbulence.cli chart --ytd --output ~/Desktop/turbulence.png
```

**Chart Features:**
- Color-coded regime zones (green=low, yellow=normal, orange=elevated, red=extreme)
- Composite turbulence score line with data points
- Current value annotation showing latest score and regime
- Statistics box (mean, std, min, max, number of days)
- Professional legend and formatting

**Example output:**
```
Composite Turbulence Score: 0.643
Current Regime: ELEVATED

Regime Interpretation:
  Low (0.00-0.25):      Calm markets, normal trading
  Normal (0.25-0.50):   Average volatility
  Elevated (0.50-0.75): Heightened uncertainty, reduce risk ← YOU ARE HERE
  Extreme (0.75-1.00):  Crisis conditions, defensive positioning
```

## How It Works (Technical Overview)

### Three-Tier Architecture

**Tier 1: Fast Indicators** (computed daily in seconds)
- VIX level regime (thresholds: <15, 15-20, 20-25, 25-30, >30)
- VIX term structure (VIX/VIX3M ratio - backwardation indicates stress)
- Garman-Klass volatility (OHLC-based, 8x more efficient than close-to-close)
- Rolling percentiles (auto-adapting to recent market conditions)

**Tier 2: Statistical Models** (retrain weekly/monthly)
- Hidden Markov Models (2-3 state Gaussian HMM, uses filtered probabilities)
- GJR-GARCH(1,1) with Student's t distribution (captures volatility clustering)
- Hamilton regime-switching models (Markov regression with switching variance)

**Tier 3: Multi-Asset Turbulence** (captures correlation breakdowns)
- Kritzman & Li turbulence index (Mahalanobis distance from historical mean)
- Absorption ratio (PCA-based measure of systemic fragility)
- Gaussian Mixture Models (unsupervised clustering of market states)

### Composite Scoring Formula

Weighted average of 5 normalized components (0-1 scale):

| Component | Weight | Description |
|-----------|--------|-------------|
| VIX percentile | 25% | Current VIX vs 252-day rolling distribution |
| VIX term structure | 15% | VIX/VIX3M ratio (backwardation = stress) |
| Realized volatility | 20% | Garman-Klass 30-day rolling vol percentile |
| Turbulence index | 25% | Mahalanobis distance (cross-asset correlation surprise) |
| GARCH conditional vol | 15% | GJR-GARCH forecasted volatility percentile |

**Final score = Σ(weight_i × component_i)**

Regime thresholds:
- 0.00-0.25 → Low turbulence
- 0.25-0.50 → Normal turbulence
- 0.50-0.75 → Elevated turbulence
- 0.75-1.00 → Extreme turbulence

### Avoiding Look-Ahead Bias

**Critical for real-time trading:**
- All statistics use rolling windows (30, 60, 252 days)
- HMM uses filtered probabilities (forward algorithm) NOT Viterbi decoding
- Walk-forward validation (train on 3 years, test on 6 months, step forward)
- Models retrained on expanding windows (never future data)

### Whipsaw Prevention

**Hysteresis thresholds:**
- Enter high-vol regime at VIX 28, exit at VIX 22 (prevent oscillation)
- Require 3-5 consecutive days in new regime before acting
- Use probabilistic sizing (HMM filtered probabilities) instead of hard regime switches

## Trading Applications

### ES Futures Trading

**Position Sizing:**
- Low/Normal (0-50%): Standard position size
- Elevated (50-75%): Cut risk by 25-50%
- Extreme (75-100%): Half size or stand aside

**Stop Management:**
- Low/Normal: Standard ATR-based stops
- Elevated: Widen S/R zones by 1.5× ATR (expect overshoot)
- Extreme: Only major pivots (S1/S2, R1/R2), wider stops

**Strategy Selection:**
- Low turbulence: Support/resistance bounces, tight stops
- Normal turbulence: Balanced approach, S/R + momentum
- Elevated turbulence: Momentum/breakout bias, wider stops
- Extreme turbulence: Major pivots only, avoid choppy ranges

### Options Trading

**Low-Vol Regimes (VIX < 15):**
- Buy cheap OTM puts for protection
- Sell covered calls (premium is low but safe)
- Consider debit spreads (limited risk)

**High-Vol Regimes (VIX > 25):**
- Sell premium via credit spreads (high IV crush potential)
- Use jade lizards (undefined risk but bullish bias)
- 90% of VIX > 30 spikes resolve within 3 months

**Extreme Regimes (VIX > 30):**
- Avoid naked short premium (gamma risk)
- Use protective puts or defined-risk spreads
- Wait for IV crush before selling premium

## Daily Usage Pattern

### Complete Daily Trading Workflow

This section shows how to integrate the turbulence system into your daily ES futures/options trading routine.

---

### 1. Pre-Market Preparation (6:00 AM - 9:30 AM ET)

**Step 1: Update Market Data (2 minutes)**

```bash
# Activate environment
source .venv/bin/activate

# Fetch latest data (includes yesterday's close and pre-market if available)
python -m turbulence.cli fetch-data

# Output example:
# ✓ Successfully fetched 7 tickers
#   Total rows: 7
#   Inserted: 7, Updated: 0
#   Date range: 2026-02-10 to 2026-02-10
```

**Step 2: Recompute All Indicators (30-60 seconds)**

```bash
# IMPORTANT: Compute ALL indicators (not just tier1)
# The composite score requires all tiers
python -m turbulence.cli compute

# Output:
# Computing all indicators...
# Computing Tier 1 indicators...
#   ✓ Tier 1 complete
# Computing Tier 2 models...
#   ✓ Tier 2 complete (GARCH)
# Computing Tier 3 turbulence...
#   ✓ Tier 3 complete
# Computing composite turbulence scores...
#   ✓ Composite scoring complete
#   ✓ Stored 1 regime records
```

**Why compute all tiers daily?**
- Composite score = weighted average of all 5 components
- Tier 1 only = VIX + realized vol (40% of score)
- Missing tier 2/3 = old GARCH + turbulence data (60% of score!)
- Result: stale composite score = bad trading decisions

**Step 3: Check Current Regime (5 seconds)**

```bash
# Get detailed status
python -m turbulence.cli status --detailed

# Save output for reference during trading day
python -m turbulence.cli status --detailed > ~/trading/turbulence_$(date +%Y%m%d).txt
```

**Step 4: Interpret Results and Plan Day**

Based on the regime output, determine your trading approach:

| Regime | Score | Position Size | Stop Width | Strategy Focus |
|--------|-------|---------------|------------|----------------|
| **Low** | 0.00-0.25 | 100% standard | 1.0× ATR | S/R bounces, tight stops |
| **Normal** | 0.25-0.50 | 100% standard | 1.0× ATR | Balanced S/R + momentum |
| **Elevated** | 0.50-0.75 | 50-75% reduced | 1.5× ATR | Wider stops, major levels only |
| **Extreme** | 0.75-1.00 | 0-50% reduced | 2.0× ATR | Stand aside or major pivots |

**Example Pre-Market Analysis:**

```
Composite Turbulence Score: 0.597 (ELEVATED/EXTREME)

Component Breakdown:
  VIX: 17.36 (normal) - but contradicted by realized vol
  Realized Vol: 0.996 (99.6th percentile!) ← KEY SIGNAL
  Turbulence Index: 0.623 (elevated correlation stress)
  GARCH Vol: 0.718 (elevated forecasted vol)

DECISION FOR TODAY:
  ✗ Reduce position size to 50%
  ✗ Widen stops to 1.5× normal ATR
  ✗ Only trade clear S1/S2, R1/R2 levels
  ✗ Skip marginal setups
  ✗ Avoid choppy midday ranges
  ✓ Be patient, wait for A+ setups
```

---

### 2. Market Open Analysis (9:30 AM - 10:00 AM ET)

**Check if overnight regime still valid:**

```bash
# If major gap or news event occurred, recheck
python -m turbulence.cli status --detailed
```

**Adjust intraday plan based on opening action:**

- **Low/Normal regime + gap up/down:** Consider fade if overbought/oversold
- **Elevated/Extreme regime + gap:** Wait for confirmation, expect whipsaws
- **Regime change overnight:** Re-evaluate position sizes before entering trades

---

### 3. Intraday Monitoring (10:00 AM - 4:00 PM ET)

**No need to run commands during trading hours** - the regime classification is stable throughout the day.

**Use pre-market assessment to guide decisions:**

**Low Turbulence (0.00-0.25):**
- ✓ Take S/R bounce setups at key levels
- ✓ Use tight stops (0.75-1.0× ATR)
- ✓ Scale into winners aggressively
- ✓ Target R2/R3 on strong trends
- ⚠ Still respect major pivots

**Normal Turbulence (0.25-0.50):**
- ✓ Balanced approach: S/R + momentum
- ✓ Standard stop widths (1.0× ATR)
- ✓ Normal position sizing
- ✓ Follow your usual playbook
- ⚠ Be selective on choppy days

**Elevated Turbulence (0.50-0.75):**
- ⚠ Cut position sizes by 25-50%
- ⚠ Widen stops to 1.5× ATR (expect level overshoot)
- ⚠ Only trade major S1/S2, R1/R2 levels
- ⚠ Skip B/C grade setups entirely
- ⚠ Expect false breakouts and whipsaws
- ✓ Momentum/breakout setups may work better than bounces
- ✗ Avoid trading in choppy ranges

**Extreme Turbulence (0.75-1.00):**
- ✗ Consider standing aside entirely
- ✗ If trading, use 0-50% position size
- ✗ Only major macro pivots (S2/R2, round numbers)
- ✗ Widen stops to 2.0× ATR
- ✗ Expect violent whipsaws and level overshoot
- ✗ No scalping - only high-conviction swings
- ✓ Protect capital first, profit second

**Intraday Checklist (Mental):**

Before each trade, ask:
1. Does this fit today's regime guidance?
2. Am I using the correct position size for this regime?
3. Are my stops wide enough for current volatility?
4. Is this setup A+ quality, or am I forcing it?
5. If regime is elevated/extreme, should I skip this?

---

### 4. Post-Market Analysis (4:00 PM - 5:00 PM ET)

**Review Day's Performance:**

```bash
# Check if regime changed intraday (rare, but possible)
python -m turbulence.cli status --detailed

# Compare today's regime to previous days
python -m turbulence.cli status --date $(date -d "yesterday" +%Y-%m-%d) --detailed
```

**Journal Questions:**

1. Did I respect the pre-market regime assessment?
2. Did I adjust position sizes appropriately?
3. Were my stops too tight for the regime?
4. Did I take marginal setups I should have skipped?
5. How did price action align with turbulence forecast?

**If regime was elevated/extreme:**
- Did major levels hold or get violated?
- Were there whipsaws as expected?
- Did I avoid overtrading?

---

### 5. End-of-Week Analysis (Friday Evening)

**Full System Update:**

```bash
# 1. Full historical refresh (in case of data gaps)
python -m turbulence.cli fetch-data --start-date 2020-01-01

# 2. Retrain statistical models (GARCH, HMM)
python -m turbulence.cli compute --retrain

# 3. Check regime trend over past week
for date in $(seq 5 -1 0); do
  d=$(date -d "$date days ago" +%Y-%m-%d)
  echo "=== $d ==="
  python -m turbulence.cli status --date $d
  echo
done
```

**Review Regime Trend:**

- **Regime increasing:** Market stress building, reduce exposure into next week
- **Regime decreasing:** Stress resolving, can increase exposure
- **Regime stable:** Continue current approach
- **Regime whipsawing:** Wait for clarity before increasing size

---

### 6. Monthly Model Maintenance (First Sunday of Month)

```bash
# 1. Full data refresh
python -m turbulence.cli fetch-data --start-date 2020-01-01

# 2. Retrain all models with full history
python -m turbulence.cli compute --retrain --indicators all

# 3. Validate current regime
python -m turbulence.cli status --detailed
```

**Model Health Check:**

- Are GARCH parameters stable? (alpha + beta < 1.0)
- Is HMM converging? (check log-likelihood trends)
- Is turbulence index showing realistic values? (not stuck at extremes)
- Do regime transitions match intuition? (check major recent events)

---

### 7. Example Trading Day Scenarios

**Scenario A: Low Turbulence Day**

```
06:30 AM - Pre-market routine
  Regime: Low (0.18)
  VIX: 12.5
  Decision: Normal trading, full size

09:30 AM - Market opens flat
  Plan: Look for S/R bounces at 4950 (S1) and 5000 (R1)

10:15 AM - ES bounces cleanly off 4950
  Entry: Long at 4952
  Stop: 4948 (1.0× ATR = 4 points)
  Target: 4970 (midpoint)
  Size: 100% standard (2 contracts for this example)

11:45 AM - Target hit, +18 points
  Exit: 4970, book profit

Outcome: Standard S/R bounce worked as expected in low-vol regime
```

**Scenario B: Elevated Turbulence Day**

```
06:30 AM - Pre-market routine
  Regime: Elevated (0.63)
  VIX: 22.8
  Realized Vol: 88th percentile
  Decision: Cut size to 50%, widen stops

09:30 AM - Market gaps down 20 points
  Plan: Wait for major pivot test (S2 at 4920)

10:30 AM - ES tests 4920, shows support
  Entry: Long at 4922
  Stop: 4914 (1.5× ATR = 8 points) ← WIDER than normal
  Target: 4945 (S1 level)
  Size: 50% (1 contract instead of 2) ← REDUCED

11:15 AM - Whipsaw drops to 4918, stop NOT hit due to wider stop
  Hold position (would have been stopped out with normal stop)

12:30 PM - Rally to 4944
  Exit: 4944, book profit

Outcome: Wider stops and reduced size protected against volatility
```

**Scenario C: Extreme Turbulence Day**

```
06:30 AM - Pre-market routine
  Regime: Extreme (0.81)
  VIX: 35.2
  Turbulence Index: 92nd percentile
  Decision: Stand aside or 25% size only

09:30 AM - Market gaps down 40 points, violent whipsaws
  Plan: No trading unless CLEAR S2/R2 test

10:45 AM - ES tests major S2 at 4850
  Temptation: Long setup forming
  Decision: PASS - regime too extreme, size would be 25% (< 1 contract)

11:30 AM - Violent whipsaw: +25, -30, +15 within 20 minutes
  Outcome: Avoided unpredictable chop

2:00 PM - Market finds footing at S2
  Entry: STILL PASS - wait for regime to drop below 0.75 tomorrow

End of Day: Sat out, preserved capital
  Tomorrow: Check if regime improved

Outcome: Avoided high-risk environment, no trades = no losses
```

---

### 8. Automation Ideas

**Cron Job for Automatic Updates (Optional):**

```bash
# Add to crontab (crontab -e)
# Run at 6:00 AM ET every weekday
0 6 * * 1-5 cd /home/user/code/turbulence && source .venv/bin/activate && python -m turbulence.cli fetch-data && python -m turbulence.cli compute --indicators tier1

# Email results (requires mail setup)
5 6 * * 1-5 cd /home/user/code/turbulence && source .venv/bin/activate && python -m turbulence.cli status --detailed | mail -s "Turbulence Regime $(date +\%Y-\%m-\%d)" your@email.com
```

**Shell Script for Quick Check:**

```bash
#!/bin/bash
# Save as ~/trading/turbulence-check.sh

cd /home/user/code/turbulence
source .venv/bin/activate

echo "Fetching latest data..."
python -m turbulence.cli fetch-data > /dev/null 2>&1

echo "Computing indicators..."
python -m turbulence.cli compute --indicators tier1 > /dev/null 2>&1

echo ""
echo "===================================="
echo "  TURBULENCE REGIME - $(date +%Y-%m-%d)"
echo "===================================="
python -m turbulence.cli status --detailed

# Make executable: chmod +x ~/trading/turbulence-check.sh
# Run: ~/trading/turbulence-check.sh
```

---

### 9. Trading Psychology Tips by Regime

**Low/Normal (0-50%):**
- ✓ Trade with confidence
- ✓ Your edge is working
- ✓ Follow your normal process
- ⚠ Don't overtrade just because conditions are good

**Elevated (50-75%):**
- ⚠ Stay defensive
- ⚠ Smaller size = less stress
- ⚠ Wider stops = fewer whipsaws
- ⚠ Be patient, wait for quality
- ✓ It's okay to skip marginal setups

**Extreme (75-100%):**
- ✗ When in doubt, stay out
- ✗ Preservation over profit
- ✗ No FOMO - market will be here tomorrow
- ✗ You can't trade if you blow up the account
- ✓ Cash is a position
- ✓ Living to trade another day is success

**Remember:** The turbulence system is a **risk management tool**, not a crystal ball. It tells you when to be cautious, not when to force trades. Your edge comes from combining regime awareness with your own technical analysis and order flow reading.

---

## Common Workflows

### Weekly Analysis

```bash
# 1. Full data refresh (all tickers, full history)
python -m turbulence.cli fetch-data --start-date 2020-01-01

# 2. Retrain statistical models
python -m turbulence.cli compute --retrain

# 3. Generate report (when implemented)
# python -m turbulence.cli report --output weekly_report.html
```

### Monthly Model Retraining

```bash
# 1. Fetch full dataset
python -m turbulence.cli fetch-data

# 2. Retrain all models (GARCH, HMM, regime-switching)
python -m turbulence.cli compute --retrain --indicators all

# 3. Validate model fit (check BIC, log-likelihood)
# Use walk-forward backtest to verify performance
```

## Database Schema

### Your Existing Tables (Not Modified)

- **stock_prices** - OHLCV data for all tickers (ticker, date, open, high, low, close, volume)

### New Turbulence Tables

**turbulence_volatility_metrics**
```sql
ticker, date, garman_klass_vol, parkinson_vol, rogers_satchell_vol,
yang_zhang_vol, close_to_close_vol, vol_percentile
```

**turbulence_regime_classifications**
```sql
date, vix_level, vix3m_level, vix_term_structure_ratio, vix_regime,
realized_vol_percentile, garch_conditional_vol, turbulence_index,
hmm_state, hmm_prob_low, hmm_prob_normal, hmm_prob_high, absorption_ratio
```

**turbulence_composite_scores**
```sql
date, vix_component, vix_term_component, realized_vol_component,
turbulence_component, garch_component, composite_score, regime_label
```

## Configuration

### Environment Variables (.env)

```bash
# Optional: custom data directory (default: ~/.turbulence/data)
TURBULENCE_DATA_DIR=/path/to/data

# Optional: FRED API (for credit spreads, yield curve)
FRED_API_KEY=your_fred_api_key

# Optional: logging
LOG_LEVEL=INFO
```

### Default Tickers

The system fetches these tickers by default (required for turbulence index):

- **SPY** - S&P 500 ETF (equity market proxy)
- **TLT** - 20+ Year Treasury Bond ETF (long-duration bonds)
- **GLD** - Gold ETF (safe haven asset)
- **UUP** - US Dollar Index (currency)
- **HYG** - High Yield Corporate Bond ETF (credit risk)
- **^VIX** - CBOE Volatility Index (implied volatility)
- **^VIX3M** - CBOE 3-Month Volatility Index (term structure)

## Troubleshooting

### "No price data found"

```bash
# Fetch data first
python -m turbulence.cli fetch-data --start-date 2020-01-01
```

### "No regime data found"

```bash
# Run computation first
python -m turbulence.cli compute
```

### "Module not found" errors

```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Data fetching fails

Check that:
- yfinance can reach Yahoo Finance servers
- Data directory exists (`turbulence init`)

## Academic References

**Core methodology:**
- Kritzman, M., & Li, Y. (2010). "Skulls, Financial Turbulence, and Risk Management"
- Hamilton, J. D. (1989). "A New Approach to the Economic Analysis of Nonstationary Time Series"
- Ang, A., & Bekaert, G. (2002). "Regime Switches in Interest Rates"
- Kritzman, M., Li, Y., Page, S., & Rigobon, R. (2011). "Principal Components as a Measure of Systemic Risk"

**Volatility estimation:**
- Garman, M. B., & Klass, M. J. (1980). "On the Estimation of Security Price Volatilities from Historical Data"
- Parkinson, M. (1980). "The Extreme Value Method for Estimating the Variance of the Rate of Return"
- Rogers, L. C. G., & Satchell, S. E. (1991). "Estimating Variance from High, Low and Closing Prices"

## Next Steps

1. **Set up daily automation** - Cron job to fetch data and compute indicators pre-market
2. **Build Streamlit dashboard** - Real-time regime visualization with historical charts
3. **Implement backtesting** - Walk-forward validation to tune component weights
4. **Add alerts** - Email/SMS notifications when regime changes
5. **Integrate with broker API** - Automatic position sizing based on current regime

## Support

For issues or questions:
- Check `CLAUDE.md` for detailed architectural documentation
- Review `TURBULENCE.md` for academic/theoretical background
- Inspect `DATABASE_README.md` for database layer details
- Check logs in `~/.turbulence/logs/` (if configured)

**Remember:** This system is a decision support tool, not a black box. Always validate regime classifications against current market conditions and use human judgment before adjusting positions.
