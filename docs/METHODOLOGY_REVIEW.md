# Scientific Methodology Review: Turbulence Regime Detection System

## Overview

This document reviews the market turbulence regime detection system from a
quantitative finance and statistical methodology perspective, identifies
strengths and weaknesses, and proposes concrete next steps ranked by scientific
interest and practical value.

---

## 1. What the System Does Well

### 1.1 Multi-Scale, Multi-Source Signal Design

The three-tier architecture is the strongest design choice in the system.
Single-indicator regime detection is fragile — VIX alone misses correlation
breakdowns, GARCH alone misses implied-vol signals, and the Mahalanobis
turbulence index alone cannot capture single-asset microstructure stress.
By stacking three tiers with different information sources (implied vol,
realized vol, cross-asset covariance structure) and different timescales
(instantaneous VIX thresholds vs. 500-day absorption ratio), the system
achieves genuine signal diversity.

This mirrors the academic consensus: Ang & Bekaert (2002, 2004) showed that
no single factor captures all dimensions of market regime, and that composite
approaches dominate in out-of-sample tests.

### 1.2 Rigorous Look-Ahead Bias Prevention

The codebase demonstrates unusually strong discipline against look-ahead bias:

- **HMM uses filtered probabilities** (forward algorithm) rather than Viterbi
  decoding. Viterbi optimizes over the full path including future observations —
  using it in backtests is among the most common errors in regime detection
  literature. This choice alone puts the system ahead of most retail and some
  academic implementations.

- **Rolling windows throughout**, with explicit tests (`test_lookback_fix.py`)
  that verify historical predictions are numerically stable when new data is
  appended. This is a correctness invariant that most practitioners never test.

- **Regime clustering uses expanding windows** with periodic refitting, which
  is the correct point-in-time approach for GMM (rolling GMM would produce
  unstable cluster assignments due to label switching).

### 1.3 Whipsaw Prevention via Simplicity

The 3-day persistence filter with fixed thresholds (0.25, 0.50, 0.75) is a
pragmatically sound engineering choice. More complex approaches (adaptive
hysteresis, Bayesian changepoint detection) add model complexity that is
difficult to validate out-of-sample. The system wisely avoids optimizing
these thresholds, which would introduce a subtle form of overfitting.

### 1.4 Correct GARCH Specification

Using GJR-GARCH(1,1) with Student's t innovations for equity index data is
the consensus choice in the volatility modeling literature. The leverage
effect (asymmetric volatility response to positive vs. negative shocks)
is a well-documented empirical regularity in equity indices, and the Student's t
distribution handles the excess kurtosis that Gaussian GARCH systematically
underestimates in tails.

The detail of scaling returns to percentages before fitting the `arch` library
is a practical necessity that many implementations overlook, leading to
convergence failures or numerically degenerate parameter estimates.

---

## 2. Methodological Weaknesses and Concerns

### 2.1 Composite Weights Are Ad Hoc (Moderate Concern)

The five component weights (25%, 15%, 20%, 25%, 15%) are stated as reflecting
the "complementary nature" of the signals, but there is no formal justification.
This is not unusual in practitioner systems, but it creates several issues:

- **No sensitivity analysis**: How much does regime classification change if
  the turbulence index weight moves from 25% to 35%? If the answer is "a lot,"
  the system's outputs are fragile to a subjective choice.

- **Implicit independence assumption**: Weighted averaging assumes components
  contribute independently. But VIX percentile and GARCH vol percentile are
  highly correlated (both respond to the same equity volatility). The effective
  weight on equity vol signals is ~60% (VIX 25% + realized vol 20% + GARCH 15%),
  while the cross-asset structural signal (turbulence index) gets only 25%.

- **Equal-contribution alternatives exist**: Inverse-volatility weighting or
  PCA-based weighting on the normalized components would be more principled,
  though they introduce estimation error.

### 2.2 Percentile Normalization Has Edge Effects (Minor Concern)

All components are normalized via 252-day rolling percentile rank. This means:

- **The first 252 days produce NaN** — no regime signal at inception or after
  data gaps. For a system meant to detect crises, the initialization period is
  a blind spot.

- **Percentile normalization is uniform by construction** — it maps any
  distribution to [0, 1] uniformly over the lookback. This destroys magnitude
  information. A VIX spike from 15 to 40 (historically extreme) and a VIX
  move from 15 to 22 (common) could produce similar percentile ranks if the
  lookback window happened to contain a previous spike to 38.

- **Regime thresholds interact non-obviously with percentile windows**: If the
  last 252 days were all high-vol, a 90th-percentile VIX reading could
  correspond to a level the system would classify as merely "normal" — because
  the percentile ranking adapts. This is both a feature (adaptation) and a bug
  (loss of absolute anchoring).

### 2.3 No Model Selection or Diagnostic Reporting (Significant Gap)

The design document mentions BIC-based model selection for HMM and GARCH, but
the implementation does not include it:

- **HMM n_states is hard-coded** (2 or 3). In practice, the optimal number of
  states varies across time periods. A 2015–2019 sample may support only 2
  states, while a 2007–2012 sample may support 4.

- **GARCH specification is fixed** as GJR-GARCH(1,1). No comparison against
  EGARCH, TGARCH, or higher-order specifications is performed.

- **No goodness-of-fit diagnostics** are reported: no likelihood values, no
  information criteria, no residual analysis. For a probabilistic system, this
  makes it impossible to assess whether the models are fitting well on current
  data.

### 2.4 Absorption Ratio Window Is Very Long (Design Tension)

The 500-day (2-year) window for the absorption ratio means the signal is
extremely slow-moving. Kritzman et al. (2011) found that AR shifts preceded
crashes, but their analysis used full-sample PCA. The rolling-window version
trades look-ahead bias prevention for signal latency. During the initial COVID
shock (Feb–Mar 2020), the AR with a 500-day window would have been dominated
by the preceding low-vol regime, potentially delaying the fragility signal.

This is a fundamental tension: shorter windows increase responsiveness but also
noise; longer windows increase stability but may miss rapid structural shifts.

### 2.5 Regime Clustering Stability (HMM and GMM Label Switching)

Both HMM and GMM suffer from the label-switching problem: fitting the same
model to slightly different data can produce states with permuted labels. The
code addresses this for HMM (sorting states by covariance determinant), but:

- **GMM cluster labels may not be consistent** across refitting windows. State 0
  on one day could correspond to state 2 on the next refitting day. The code
  uses expanding windows and refits every 5 days, which reduces but does not
  eliminate this problem.

- **No alignment procedure** is implemented to match clusters across refits
  (e.g., Hungarian algorithm on cluster centroids).

### 2.6 No Evaluation of Regime Accuracy

The backtest module (`backtest.py`) tracks regime distribution and transition
counts per window but does not measure the **predictive accuracy** of regime
classifications:

- No comparison of predicted regimes against realized volatility, drawdowns,
  or tail events.
- No regime-conditional return analysis (what is the mean return and volatility
  in each classified regime?).
- No false-positive / false-negative analysis for extreme regime detection.
- No comparison against naive baselines (e.g., "always normal" or "threshold
  on trailing 20-day realized vol").

### 2.7 Single Equity Index Focus

The system is built around ES/SPY. The cross-asset basket (SPY, TLT, GLD, UUP,
HYG) is reasonable for detecting systemic stress, but:

- **No credit-specific indicators**: High-yield spread (BAMLH0A0HYM2) is
  mentioned in the design document but not implemented. Credit spreads are among
  the most reliable leading indicators of equity stress.

- **No yield curve signal**: The 10Y-2Y spread (T10Y2Y) is absent. Yield curve
  inversion has historically preceded recessions and equity drawdowns.

- **VIX is both a basket member and a standalone indicator**: Including VIX
  level changes in the Tier 3 Mahalanobis calculation while also using VIX
  directly in Tier 1 introduces correlation between tiers that the composite
  weighting doesn't account for.

---

## 3. Most Interesting Next Steps (Scientific Value)

These extensions would deepen the system's theoretical foundations and could
yield publishable insights.

### 3.1 Regime-Conditional Return Distribution Analysis

**What**: For each classified regime (low/normal/elevated/extreme), compute the
empirical distribution of forward 1-day, 5-day, and 21-day returns. Test
whether the distributions are statistically distinct using Kolmogorov-Smirnov
tests or permutation tests.

**Why**: This is the fundamental test of whether the regime classification
has any predictive content. If the forward return distributions do not differ
meaningfully across regimes, the system is producing labels without economic
value. If they do differ — particularly if tail risk is concentrated in elevated
and extreme regimes — this validates the entire architecture.

**Effort**: Medium (1–2 days). Uses existing regime classifications and price
data.

### 3.2 Bayesian Online Changepoint Detection

**What**: Replace or supplement the 3-day persistence filter with a Bayesian
online changepoint detection algorithm (Adams & MacKay, 2007). This approach
maintains a posterior distribution over the "run length" (time since last
changepoint) and can detect regime transitions with calibrated uncertainty.

**Why**: The current persistence filter is a crude binary gate. Bayesian
changepoint detection provides a probability that a regime change has occurred,
enabling continuous-valued position sizing adjustments rather than discrete
regime transitions. It also naturally adapts its sensitivity to the volatility
of the underlying signal.

**Effort**: High (1 week). Requires implementing the BOCPD algorithm and
integrating it with the composite score time series.

### 3.3 Information-Theoretic Component Weighting

**What**: Replace fixed weights with data-driven weights based on mutual
information between each component and realized future volatility (or
drawdowns). Use walk-forward estimation: compute mutual information on the
training window and apply the resulting weights to the test window.

**Why**: This would answer the key question: "Which components actually carry
predictive information, and how much?" It might reveal, for instance, that the
turbulence index carries 3x more predictive information than VIX percentile,
or that GARCH vol adds nothing beyond realized vol. It would also reveal
whether the optimal weights are stable across time or shift with market
structure.

**Effort**: High (3–5 days). Requires mutual information estimation (e.g.,
`sklearn.feature_selection.mutual_info_regression`) within the walk-forward
framework.

### 3.4 Spectral Analysis of Regime Durations

**What**: Analyze the distribution of regime durations (how long does each
regime last?) and compare against theoretical predictions from the HMM
transition matrix. Fit regime durations to a geometric distribution (HMM
assumption) and test whether the data supports heavier tails (e.g., power-law
or Weibull durations).

**Why**: If regime durations are geometrically distributed, the HMM is
well-specified. If they follow a power law (as some evidence suggests for
financial regimes), the HMM's memoryless transition assumption is wrong, and
a hidden semi-Markov model (HSMM) would be more appropriate. This analysis
would inform whether the system's fundamental modeling assumption holds.

**Effort**: Medium (2–3 days). Primarily analytical, using existing regime
classifications.

### 3.5 Non-Gaussian Copula-Based Turbulence Index

**What**: Replace the Mahalanobis distance (which assumes multivariate
normality) with a turbulence measure based on empirical copulas or vine
copulas. The copula approach separates marginal behavior from dependence
structure, allowing the system to detect changes in dependence without
being confounded by changes in marginal volatility.

**Why**: The Mahalanobis distance conflates two types of "turbulence": (a)
large moves in individual assets and (b) unusual dependence patterns. During
a crisis, both happen simultaneously, but for early warning, changes in
dependence structure (tail dependence, asymmetric correlations) often precede
large moves. A copula-based measure could provide earlier detection.

**Effort**: Very high (1–2 weeks). Requires copula estimation library (e.g.,
`pyvinecopulib`) and careful rolling-window estimation.

---

## 4. Most Practical Next Steps (Trading Value)

These extensions would directly improve the system's utility for ES/options
trading decisions.

### 4.1 Credit Spread Integration (Highest Priority)

**What**: Add the ICE BofA US High Yield Option-Adjusted Spread
(BAMLH0A0HYM2, available free via FRED) as a Tier 1 indicator. Compute its
percentile rank and add it to the composite score as a sixth component.

**Why**: Credit spreads are among the most reliable leading indicators of
equity stress. They typically widen before equity volatility spikes because
credit markets price default risk before equity markets price drawdown risk.
The HYG price already in the Tier 3 basket captures some of this, but the
option-adjusted spread is a cleaner, more direct signal that doesn't require
Mahalanobis distance computation to interpret.

**Implementation**:
```python
# In data_fetcher.py, add FRED integration
from fredapi import Fred
fred = Fred(api_key=os.environ.get('FRED_API_KEY'))
hy_spread = fred.get_series('BAMLH0A0HYM2')
```

Add to composite with ~10% weight, reducing VIX and realized vol weights
proportionally.

**Effort**: Low (half a day). Requires `fredapi` and a free FRED API key.

### 4.2 Regime-Aware Position Sizing Module

**What**: Implement the probabilistic position sizing that the design document
describes but the code doesn't implement. Instead of discrete regime labels,
use the continuous composite score (or HMM filtered probabilities directly)
to compute a position size multiplier:

```python
def position_multiplier(composite_score: float, max_reduction: float = 0.75) -> float:
    """
    Returns multiplier in [1 - max_reduction, 1.0].
    Score of 0 → full size. Score of 1 → minimum size.
    """
    return 1.0 - max_reduction * composite_score
```

**Why**: The design document explicitly recommends probabilistic sizing over
hard regime labels to prevent whipsaw in position management. This is the
primary intended use case of the system and it's not implemented.

**Effort**: Low (1 day). A thin module that maps composite scores to trading
parameters (position size multiplier, stop width multiplier, strategy
selector).

### 4.3 Regime Transition Alerts

**What**: Add a notification layer that detects when the composite score is
approaching a regime boundary (within 0.05 of a threshold) or when the
persistence filter is counting consecutive days in a new regime (day 1 of 3,
day 2 of 3).

**Why**: The current system reports the regime *after* the persistence filter
confirms it. For trading, you need early warning: "The composite score has
been in elevated territory for 2 consecutive days; one more day confirms the
regime transition." This gives traders a day to prepare stop adjustments and
position reductions.

**Implementation**: Add to the `compute` output a `regime_transition_warning`
field with values like `"approaching_elevated (2/3 days)"`.

**Effort**: Low (half a day). Straightforward extension of the persistence
filter logic.

### 4.4 Intraday Regime Check via VIX

**What**: Add a lightweight `turbulence check` command that fetches current VIX
from Yahoo Finance and computes where it falls relative to the most recent
252-day distribution, without running the full pipeline.

**Why**: The full `compute` pipeline requires end-of-day data for OHLCV,
multi-asset returns, and model refitting. But an intraday trader needs a quick
read during market hours. A VIX-only check (Tier 1 signals only) with
pre-computed percentile thresholds gives a useful real-time approximation.

**Effort**: Low (half a day).

### 4.5 Realized vs. Predicted Volatility Tracking

**What**: After each trading day, compare the system's regime classification
against what actually happened: compute realized volatility over the next
5 and 21 days and track whether "extreme" regime classifications were
followed by genuinely extreme realized vol (and conversely, whether "low"
regimes stayed calm).

**Why**: This is the operational feedback loop that turns the system from a
static tool into a continuously validated one. If extreme classifications are
followed by normal markets 40% of the time, the system is too sensitive and
the thresholds or weights need adjustment.

**Implementation**: Add a `turbulence validate` command that computes
forward-looking hit rates for each regime:

| Regime     | Forward 5d vol (ann.) | Forward 21d vol (ann.) | Forward max drawdown |
|-----------|----------------------|----------------------|---------------------|
| Low       | 8.2%                 | 9.1%                 | -1.8%               |
| Normal    | 14.5%                | 15.2%                | -3.4%               |
| Elevated  | 22.1%                | 24.8%                | -6.2%               |
| Extreme   | 38.7%                | 35.4%                | -12.1%              |

**Effort**: Medium (1–2 days).

### 4.6 EGARCH Variant and Model Comparison

**What**: Add EGARCH as an alternative to GJR-GARCH and implement BIC-based
model selection in the rolling GARCH computation.

**Why**: EGARCH models log-volatility, avoiding the positivity constraints
that occasionally cause numerical issues in GARCH estimation. More importantly,
implementing model comparison closes the gap between what the design document
promises and what the code delivers. In practice, GJR-GARCH and EGARCH often
produce very similar conditional volatility series for equity indices, so
the primary value is robustness rather than accuracy gains.

**Effort**: Low–Medium (1 day). The `arch` library supports EGARCH via
`vol='EGARCH'`.

---

## 5. Prioritized Roadmap

| Priority | Step | Type | Effort | Impact |
|----------|------|------|--------|--------|
| 1 | Regime-conditional return analysis (3.1) | Scientific | Medium | Validates the entire system |
| 2 | Credit spread integration (4.1) | Practical | Low | Adds leading indicator |
| 3 | Position sizing module (4.2) | Practical | Low | Closes design-implementation gap |
| 4 | Realized vs. predicted tracking (4.5) | Both | Medium | Operational feedback loop |
| 5 | Regime transition alerts (4.3) | Practical | Low | Trading usability |
| 6 | EGARCH + model selection (4.6) | Both | Low–Med | Robustness |
| 7 | Spectral analysis of durations (3.4) | Scientific | Medium | Tests HMM assumptions |
| 8 | Information-theoretic weights (3.3) | Scientific | High | Principled weighting |
| 9 | Intraday VIX check (4.4) | Practical | Low | Real-time usability |
| 10 | Bayesian changepoint detection (3.2) | Scientific | High | Replaces persistence filter |
| 11 | Copula-based turbulence (3.5) | Scientific | Very High | Early warning improvement |

The first four items form a natural sequence: validate the system's predictions
(3.1), add the best missing input (4.1), implement the primary output (4.2),
and close the feedback loop (4.5). Together they would transform the system
from a research prototype into a production-grade trading tool.

---

## 6. Summary Judgment

The system is well-designed, avoids the most common pitfalls in regime
detection (look-ahead bias, overfitted thresholds, single-indicator fragility),
and is built on solid academic foundations. The three-tier architecture with
Mahalanobis turbulence as the centerpiece is the right design for an
ES-focused regime detection system.

The most significant gap is the absence of any predictive validation — the
system produces regime labels but never checks whether those labels correspond
to meaningfully different forward-looking return or risk distributions. This
should be the first priority.

The most impactful practical addition would be credit spreads (cheap to add,
high marginal signal value) followed by implementing the probabilistic position
sizing that the design document envisions but the code omits.
