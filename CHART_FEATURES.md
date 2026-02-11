# Turbulence Chart Features - Summary

## What Was Added

### 1. Chart Generation Script (`plot_turbulence.py`)

A standalone Python script that creates beautiful turbulence charts with:

**Visual Features:**
- ✅ Color-coded regime zones (green, yellow, orange, red)
- ✅ Composite turbulence score line with data points
- ✅ Current value annotation with regime label
- ✅ Statistics box (mean, std, min, max, days)
- ✅ Clean legend explaining each regime
- ✅ Professional formatting with grid and labels

**Usage:**
```bash
# Year-to-date
python plot_turbulence.py --ytd --output turbulence_ytd.png

# Last 3 months
python plot_turbulence.py --start-date 2025-11-01 --output turbulence_3m.png

# Custom date range
python plot_turbulence.py --start-date 2024-01-01 --end-date 2024-12-31 --output 2024.png

# Display on screen (no file output)
python plot_turbulence.py --ytd
```

### 2. CLI Subcommand (`turbulence chart`)

Integrated chart generation into the main CLI with convenient shortcuts:

```bash
# Year-to-date (most common)
turbulence chart --ytd

# Last 3 months
turbulence chart --last-3m

# Last 6 months
turbulence chart --last-6m

# Custom date range
turbulence chart --start-date 2024-01-01 --end-date 2024-12-31

# Save to specific file
turbulence chart --ytd --output ~/Desktop/turbulence.png
```

**Automatic Output Naming:**
- `--ytd` → saves as `turbulence_ytd_2026.png`
- `--last-3m` → saves as `turbulence_3months.png`
- `--last-6m` → saves as `turbulence_6months.png`

### 3. Fixed `--date` Parameter in `status` Command

Previously broken, now works correctly:

```bash
# Check specific date
turbulence status --date 2024-02-05

# Compare different dates
turbulence status --date 2026-01-15  # 0.160 (LOW)
turbulence status --date 2026-02-09  # 0.483 (ELEVATED)
```

## Example Charts Generated

### Year-to-Date Chart (2026-01-01 to 2026-02-10)

Shows 27 data points with:
- **Mean:** 0.333
- **Latest:** 0.473 (ELEVATED)
- **Range:** 0.115 to 0.652

Key insights:
- Started year in LOW regime (0.16)
- Gradual increase through January
- Sharp spike to 0.65 in late January
- Currently elevated at 0.47

### 3-Month Chart (2025-11-13 to 2026-02-11)

Shows 60 data points with:
- **Mean:** 0.371
- **Latest:** 0.473 (ELEVATED)
- **Range:** 0.115 to 0.705

Key insights:
- High volatility in November (0.65-0.70 range)
- Calm period December-January (dropped to 0.16)
- Recent spike back to elevated levels
- Clear whipsaw pattern visible

## Technical Details

### Chart Components

**Regime Zones (Background Shading):**
- Low (0.00-0.25): Light green (#90EE90)
- Normal (0.25-0.50): Gold (#FFD700)
- Elevated (0.50-0.75): Orange (#FFA500)
- Extreme (0.75-1.00): Red-orange (#FF4500)

**Line Plot:**
- Color: Dark blue (#2E4057)
- Line width: 2px
- Markers: Small dots at each data point
- Z-order: Above background, below annotations

**Annotations:**
- Latest value box: Yellow background with arrow
- Statistics box: White background, bottom-right corner
- Grid: Dotted lines, light gray, 30% opacity

**Threshold Lines:**
- Dashed gray lines at 0.25, 0.50, 0.75
- Help visualize regime boundaries

### Dependencies Added

Updated `requirements.txt`:
```
matplotlib  # Chart generation
pandas      # Already present, used for data handling
```

## Integration with Workflows

### Daily Pre-Market Routine

```bash
# 1. Update data
turbulence fetch-data

# 2. Compute indicators
turbulence compute --indicators tier1

# 3. Check status
turbulence status --detailed

# 4. Generate chart for review
turbulence chart --last-3m --output ~/trading/turbulence_$(date +%Y%m%d).png
```

### Weekly Analysis

```bash
# Generate YTD and 3-month charts for comparison
turbulence chart --ytd --output weekly_ytd.png
turbulence chart --last-3m --output weekly_3m.png

# Review trends
open weekly_ytd.png weekly_3m.png
```

### Monthly Review

```bash
# Generate comprehensive chart showing full history
turbulence chart --start-date 2024-01-01 --output monthly_review.png

# Include in monthly report
```

## Use Cases

### 1. Trend Identification

Quickly see if turbulence is:
- **Increasing:** Red flag, reduce exposure
- **Decreasing:** Green light, can increase exposure
- **Stable:** Continue current approach
- **Whipsawing:** Wait for clarity

### 2. Regime Persistence

Visual confirmation of:
- How long in current regime
- Frequency of regime changes
- Stability of current regime

### 3. Historical Context

Compare current score to:
- Recent highs/lows
- Average over period
- Previous similar events

### 4. Communication

Share charts with:
- Trading team/partners
- Journal/blog
- Performance reviews
- Risk management discussions

## Tips

**Best Practices:**
- Generate charts weekly for trend review
- Compare YTD vs 3-month for different perspectives
- Look for regime clusters (long periods in one zone)
- Note sharp spikes (often precede regime changes)

**Interpretation:**
- **Smooth lines:** Stable regimes, predictable volatility
- **Jagged lines:** Volatile regimes, frequent changes
- **Sharp spikes:** Event-driven turbulence (news, macro events)
- **Gradual slopes:** Market transitioning between regimes

**Avoid:**
- Over-interpreting single-day moves
- Ignoring broader trends
- Trading against clear regime trends
- Forcing trades in extreme regimes

## Quick Reference

```bash
# Most common commands
turbulence chart --ytd              # Year-to-date
turbulence chart --last-3m          # Last 3 months
turbulence status --date 2024-02-05 # Specific date

# Full workflow
turbulence fetch-data && turbulence compute --indicators tier1 && turbulence chart --ytd
```

## Files Created/Modified

**New Files:**
- `plot_turbulence.py` - Chart generation script
- `CHART_FEATURES.md` - This documentation

**Modified Files:**
- `src/turbulence/cli.py` - Added `chart` command, fixed `status --date`
- `requirements.txt` - Added `matplotlib`

**Generated Files:**
- `turbulence_ytd_2026.png` - YTD chart
- `turbulence_3months.png` - 3-month chart

All chart files are saved in the project root by default, but you can specify any output path.
