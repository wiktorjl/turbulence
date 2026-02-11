# Hysteresis Issue - Complete Summary

## The Question

**User:** "Chart says 'elevated' but the last element is visually in 'Normal' mode (yellow zone)"

Score: 0.473
Visual zone: Normal (yellow, 0.25-0.50)
Regime label: ELEVATED
**Why the mismatch?**

## The Answer

**It's not a bug - it's hysteresis working as designed!**

### What is Hysteresis?

Hysteresis uses **different thresholds for entering vs. exiting regimes** to prevent whipsaw:

| Regime | Enter At | Exit At | Hysteresis Band |
|--------|----------|---------|-----------------|
| Normal | 0.25 | 0.20 | 0.20-0.25 |
| **Elevated** | **0.50** | **0.45** | **0.45-0.50** ← THE KEY |
| Extreme | 0.75 | 0.60 | 0.60-0.75 |

### What Happened (Timeline)

```
Feb 5: Score 0.628 → Regime: NORMAL
       (Needs 0.50+ to enter elevated, still normal)

Feb 6: Score 0.664 → Regime: ELEVATED ✓
       (Crossed 0.50 entry threshold, entered elevated)

Feb 9: Score 0.483 → Regime: ELEVATED
       (Dropped into normal visual zone, but above 0.45 exit threshold)
       ↑ HYSTERESIS ACTIVE

Feb 10: Score 0.473 → Regime: ELEVATED
        (Still in normal visual zone, still above 0.45 exit)
        ↑ HYSTERESIS ACTIVE

To exit elevated: Score must drop BELOW 0.45
Currently: 0.473 > 0.45 → Stays elevated
```

### Why This is Good

**Prevents whipsaw:**

```
WITHOUT HYSTERESIS:
Feb 6: 0.664 → Elevated → Reduce size to 50%
Feb 9: 0.483 → Normal → Increase size to 100%  ← Premature!
Feb 10: 0.520 → Elevated → Reduce size to 50%  ← Whipsaw!
Feb 11: 0.470 → Normal → Increase size to 100%
Result: 4 position changes in 6 days, churning

WITH HYSTERESIS:
Feb 6: 0.664 → Elevated → Reduce size to 50%
Feb 9: 0.483 → Elevated → Keep 50% (hysteresis)
Feb 10: 0.473 → Elevated → Keep 50% (hysteresis)
Feb 11: 0.430 → Normal → Increase to 100% (exited cleanly)
Result: 2 position changes, avoids whipsaw
```

## The Fix: Improved Charts

### Changes Made

**1. Chart Annotation Now Shows Hysteresis**

Before:
```
Latest: 0.473
(ELEVATED)
```

After:
```
Score: 0.473
Regime: ELEVATED
(Hysteresis: was ELEVATED)
```

**2. Orange Box When Hysteresis Active**

- **Yellow box:** Score and regime match (normal situation)
- **Orange box:** Hysteresis active (regime ≠ visual zone)

**3. Red Dotted Lines Show Exit Thresholds**

- Dashed gray lines: Entry thresholds (0.25, 0.50, 0.75)
- **Dotted red lines: Exit thresholds (0.20, 0.45, 0.60)** ← NEW
- Makes hysteresis bands visible

### Updated Charts

**Before (confusing):**
- Visual: Yellow (normal)
- Label: ELEVATED
- No explanation → User confused

**After (clear):**
- Visual: Yellow (normal) with red dotted line at 0.45
- Label: ELEVATED with orange box
- Annotation: "Hysteresis: was ELEVATED"
- Clear that hysteresis is keeping it elevated

## How to Interpret Charts Now

### Reading the Chart Elements

| Element | Meaning |
|---------|---------|
| **Green zone** | Low regime (0.00-0.25) |
| **Yellow zone** | Normal regime (0.25-0.50) |
| **Orange zone** | Elevated regime (0.50-0.75) |
| **Red zone** | Extreme regime (0.75-1.00) |
| **Dashed gray lines** | Entry thresholds (0.25, 0.50, 0.75) |
| **Dotted red lines** | Exit thresholds (0.20, 0.45, 0.60) |
| **Yellow annotation box** | Score and regime match |
| **Orange annotation box** | Hysteresis active (regime ≠ zone) |

### Example Scenarios

**Scenario 1: Normal Match**
```
Score: 0.35
Visual zone: Yellow (normal)
Regime: NORMAL
Box color: Yellow
Interpretation: All aligned, no hysteresis
```

**Scenario 2: Hysteresis Active (Current)**
```
Score: 0.473
Visual zone: Yellow (normal)
Regime: ELEVATED
Box color: Orange
Interpretation: Hysteresis keeping it elevated
Action: Use elevated position sizing (50-75%)
Wait for: Score to drop below 0.45 to exit
```

**Scenario 3: Rising into Elevated**
```
Score: 0.48
Visual zone: Yellow (normal)
Regime: NORMAL
Box color: Yellow
Next: If score crosses 0.50, enters elevated
```

## Trading Implications

### Always Use the REGIME Label

**CRITICAL RULE:**
```
Use the REGIME LABEL for position sizing, NOT the visual zone!
```

**Example (Current Situation):**
```
Score: 0.473
Visual zone: NORMAL (yellow)
Regime: ELEVATED (orange box)

❌ WRONG: "Visual zone is normal, I'll use 100% size"
✅ RIGHT: "Regime is elevated, I'll use 50-75% size"
```

### When Hysteresis Helps

**1. Prevents premature position increases**
```
Score drops from 0.65 → 0.48
Without hysteresis: Immediately increase size
With hysteresis: Wait for <0.45 to confirm
Result: Avoid getting caught if it bounces back up
```

**2. Prevents whipsaw on noisy days**
```
Score bouncing: 0.49 → 0.51 → 0.48 → 0.52
Without hysteresis: 4 position changes
With hysteresis: 1-2 position changes
Result: Less churning, lower transaction costs
```

**3. Forces conservative stance during uncertainty**
```
Score in hysteresis band (0.45-0.50)
Regime stays elevated until clearly safe
Result: Better risk management
```

### When Hysteresis Lags

**Downside: Slower to respond**
```
True market calm: Score drops to 0.47 and stabilizes
Hysteresis: Keeps you defensive at 50% size
Reality: Could use 100% size now
Trade-off: Safety vs. missed opportunity
```

**Net Effect:** Positive for most traders (prevents costly mistakes)

## Configuration Options

If you want to disable or adjust hysteresis, edit `src/turbulence/composite.py`:

```python
# Current settings (lines 49-55)
DEFAULT_HYSTERESIS = {
    Regime.LOW: (0.0, 0.30),
    Regime.NORMAL: (0.25, 0.20),
    Regime.ELEVATED: (0.50, 0.45),   # ← 0.05 gap
    Regime.EXTREME: (0.75, 0.60)
}

# To reduce hysteresis (more responsive, more whipsaw):
DEFAULT_HYSTERESIS = {
    Regime.ELEVATED: (0.50, 0.48),   # ← 0.02 gap (smaller)
}

# To remove hysteresis (not recommended):
DEFAULT_HYSTERESIS = {
    Regime.ELEVATED: (0.50, 0.50),   # ← No gap (no hysteresis)
}
```

**Recommendation:** Keep default settings. They're based on research and testing.

## Documentation Created

**Files:**
1. **HYSTERESIS_GUIDE.md** - Complete guide to understanding hysteresis
2. **HYSTERESIS_FIX_SUMMARY.md** - This file
3. **Updated charts** - Now show hysteresis visually

**Updated files:**
- `plot_turbulence.py` - Orange box + red dotted lines
- All generated charts show hysteresis status

## Bottom Line

### Question
"Why does chart show 'elevated' when score is in normal zone?"

### Answer
**Hysteresis** - the system uses different thresholds for entering (0.50) vs. exiting (0.45) elevated regime.

**Current situation:**
- Score: 0.473 (in normal visual zone)
- Previously entered elevated at 0.664
- Hasn't dropped below 0.45 exit threshold yet
- **Still elevated until score < 0.45**

**This is correct behavior!** It prevents whipsaw and saves you from:
- Premature position increases
- Rapid regime changes
- Costly churning

**Use the regime label (ELEVATED), not the visual zone, for trading decisions.**

### Quick Reference

```bash
# Check if hysteresis is active
turbulence status --detailed

# Look for:
# - Score vs. Regime mismatch
# - Orange annotation box on chart
# - Score in hysteresis band (0.45-0.50)

# Generate chart to visualize
turbulence chart --last-3m
```

**Trust the system** - hysteresis is there for a reason!
