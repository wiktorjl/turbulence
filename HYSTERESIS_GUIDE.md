# Understanding Hysteresis in Regime Classification

## What is Hysteresis?

Hysteresis prevents rapid regime switching due to market noise by using **different thresholds for entering vs. exiting** each regime.

Think of it like a thermostat:
- Heater turns ON at 68°F (cold threshold)
- Heater turns OFF at 72°F (warm threshold)
- Between 68-72°F: stays in whatever state it was in
- This prevents rapid on/off cycling

## Why Use Hysteresis?

**Without hysteresis:**
```
Score: 0.49 → NORMAL
Score: 0.51 → ELEVATED
Score: 0.49 → NORMAL
Score: 0.52 → ELEVATED
Score: 0.48 → NORMAL
```
Result: Whipsaw! Regime changes 5 times in 5 days.

**With hysteresis:**
```
Score: 0.49 → NORMAL (stable)
Score: 0.51 → ELEVATED (crossed 0.50 entry threshold)
Score: 0.49 → ELEVATED (above 0.45 exit threshold, stays elevated)
Score: 0.52 → ELEVATED (stable)
Score: 0.48 → ELEVATED (above 0.45 exit threshold, stays elevated)
Score: 0.43 → NORMAL (dropped below 0.45 exit threshold)
```
Result: Only 2 regime changes instead of 5. More stable.

## Threshold Table

| Regime | Visual Zone | Enter At | Exit At | Hysteresis Band |
|--------|-------------|----------|---------|-----------------|
| **Low** | 0.00-0.25 | 0.00 | 0.30 | None (always exits at 0.30) |
| **Normal** | 0.25-0.50 | 0.25 | 0.20 | **0.20-0.25** (can stay normal) |
| **Elevated** | 0.50-0.75 | 0.50 | **0.45** | **0.45-0.50** (can stay elevated) |
| **Extreme** | 0.75-1.00 | 0.75 | 0.60 | 0.60-0.75 (can stay extreme) |

## The Confusion: Score 0.473

**Visual Zone:** Normal (0.25-0.50)
**Regime Label:** ELEVATED
**Why the mismatch?**

Timeline:
```
Feb 5: Score 0.628 → Still NORMAL
       (needs >= 0.50 to enter elevated)

Feb 6: Score 0.664 → ELEVATED ✓
       (crossed 0.50 entry threshold)

Feb 9: Score 0.483 → ELEVATED
       (above 0.45 exit threshold, stays elevated)

Feb 10: Score 0.473 → ELEVATED
        (above 0.45 exit threshold, stays elevated)
        ↑
        Needs to drop below 0.45 to exit back to NORMAL
```

**Current situation:**
- Score is in "normal" visual zone (yellow)
- But regime is "elevated" due to hysteresis
- **To return to NORMAL:** score must drop below 0.45
- **Currently:** 0.473 is above 0.45, so stays elevated

## How to Read the Charts

### Chart Elements

**Background Zones (Solid Colors):**
- Green: Low (0.00-0.25)
- Yellow: Normal (0.25-0.50)
- Orange: Elevated (0.50-0.75)
- Red: Extreme (0.75-1.00)

These are the **visual/raw thresholds** without hysteresis.

**Dashed Gray Lines:**
- At 0.25, 0.50, 0.75
- **Entry thresholds** for each regime

**Dotted Red Lines:**
- At 0.20, 0.45, 0.60
- **Exit thresholds** (hysteresis boundaries)

**Annotation Box:**
- **Yellow box:** Score and regime match visual zone
- **Orange box:** Hysteresis active (regime ≠ visual zone)

### Example Interpretation

```
Score: 0.473
Regime: ELEVATED
Box color: Orange

Interpretation:
✓ Score is in Normal visual zone (yellow background)
✓ Regime is ELEVATED due to hysteresis (orange box)
✓ Previously entered elevated at 0.664
✓ Hasn't dropped below 0.45 exit threshold yet
✓ Will return to NORMAL when score drops below 0.45
```

## Trading Implications

### Use the REGIME, Not the Visual Zone

**WRONG:**
```
"Score is 0.473, that's in the normal zone (yellow).
I'll use normal position sizing (100%)."
```

**CORRECT:**
```
"Score is 0.473, but REGIME is ELEVATED (hysteresis).
I'll use elevated position sizing (50-75%)."
```

### Why This Matters

Hysteresis **intentionally lags** to prevent whipsaw:

**Scenario 1: Score dropping from elevated**
```
Day 1: 0.664 → ELEVATED → 50% position size ✓
Day 2: 0.483 → ELEVATED (hysteresis) → 50% size ✓
Day 3: 0.473 → ELEVATED (hysteresis) → 50% size ✓
Day 4: 0.430 → NORMAL (exited hysteresis) → 100% size ✓

If no hysteresis, you'd increase size on Day 2,
then get whipsawed when it spikes back up.
```

**Scenario 2: Score rising into elevated**
```
Day 1: 0.480 → NORMAL → 100% size ✓
Day 2: 0.510 → ELEVATED → 50% size ✓
Day 3: 0.490 → ELEVATED (hysteresis) → 50% size ✓
Day 4: 0.470 → ELEVATED (hysteresis) → 50% size ✓
Day 5: 0.430 → NORMAL (exited) → 100% size ✓

Hysteresis keeps you defensive until score
clearly drops below 0.45, avoiding premature scaling up.
```

## When Hysteresis Helps

**Good:** Filtering noise
```
Score bouncing: 0.48 → 0.52 → 0.49 → 0.51
Without hysteresis: 4 regime changes
With hysteresis: 1-2 regime changes
```

**Good:** Preventing premature exits
```
Elevated regime: 0.664 → 0.483 → 0.520 → 0.650
Without hysteresis: Exit at 0.483, re-enter at 0.520
With hysteresis: Stay elevated throughout
```

## When Hysteresis Lags

**Downside:** Slow to exit elevated
```
Day 1: 0.664 → ELEVATED → "Market is stressed"
Day 2: 0.483 → ELEVATED (hysteresis) → "Still elevated?"
Day 3: 0.470 → ELEVATED (hysteresis) → "Feels normal but says elevated"
Day 4: 0.430 → NORMAL → "Finally exited"

You stayed defensive on Days 2-3 even though
the market felt calmer. This is intentional!
```

**Trade-off:**
- More stability (fewer whipsaws)
- Slower to respond to genuine regime changes
- Net positive for trading (avoids costly whipsaws)

## Hysteresis Bands

### Normal ↔ Elevated Band (0.45-0.50)

**In this band:**
- If coming from NORMAL: stays NORMAL
- If coming from ELEVATED: stays ELEVATED

**Example:**
```
Score path: 0.40 → 0.48 → 0.52 → 0.48 → 0.45 → 0.48

Step by step:
0.40: NORMAL (below 0.50)
0.48: NORMAL (below 0.50 entry threshold)
0.52: ELEVATED (crossed 0.50 entry)
0.48: ELEVATED (above 0.45 exit threshold)
0.45: ELEVATED (exactly at 0.45, stays elevated)
0.48: ELEVATED (re-entered hysteresis band from elevated side)
```

To exit: must drop **below** 0.45 (not equal to).

### Low ↔ Normal Band (0.20-0.25)

**In this band:**
- If coming from LOW: stays LOW
- If coming from NORMAL: stays NORMAL

**Example:**
```
Score: 0.18 → 0.22 → 0.26 → 0.22 → 0.18

0.18: LOW
0.22: LOW (below 0.25 entry to normal)
0.26: NORMAL (crossed 0.25 entry)
0.22: NORMAL (above 0.20 exit threshold)
0.18: LOW (dropped below 0.20)
```

### Elevated ↔ Extreme Band (0.60-0.75)

**In this band:**
- If coming from ELEVATED: stays ELEVATED
- If coming from EXTREME: stays EXTREME

**Example:**
```
Score: 0.70 → 0.80 → 0.65 → 0.72

0.70: ELEVATED
0.80: EXTREME (crossed 0.75 entry)
0.65: EXTREME (above 0.60 exit threshold)
0.72: EXTREME (re-entered band from extreme side)
```

To exit extreme: must drop below 0.60.

## Summary

**Key Points:**
1. **Hysteresis is intentional** - prevents whipsaw
2. **Use the REGIME label** - not the visual zone
3. **Orange annotation box** - hysteresis is active
4. **Red dotted lines** - exit thresholds
5. **Trade-off** - stability vs. responsiveness

**For Trading:**
- Always use the regime label for position sizing
- Don't second-guess hysteresis (it's there for a reason)
- If unsure, stay conservative (use the stricter regime)
- Hysteresis saves you from costly whipsaws

**Current Example (Feb 10):**
- Score: 0.473 (in normal visual zone)
- Regime: ELEVATED (hysteresis active)
- Action: Use 50-75% position size (elevated rules)
- Wait for: Score to drop below 0.45 before increasing size
