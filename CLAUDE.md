# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **market turbulence regime detection system** for ES futures and options trading. The system combines multiple volatility indicators, statistical models, and cross-asset correlation metrics to classify market regimes (low/normal/elevated/extreme turbulence) and inform trading decisions around position sizing, stop widths, and strategy selection.

The design document (TURBULENCE.md) defines a three-tier architecture progressing from simple VIX-based indicators to advanced multi-asset turbulence indices.

## Architecture

The system is organized into three tiers of increasing sophistication:

### Tier 1: Fast Indicators (afternoon build)
- **VIX regime classification**: Threshold-based (VIX < 15 = complacent, 15-20 = normal, 20-25 = elevated, 25-30 = high, > 30 = panic)
- **VIX term structure**: VIX/VIX3M ratio detecting backwardation (stress) vs contango (calm)
- **Garman-Klass volatility**: OHLC-based estimator 8x more efficient than close-to-close, computed on rolling 30-day windows
- **Percentile-based classification**: Auto-adapting quartile-based regime detection

### Tier 2: Statistical Models (weekend build)
- **Hidden Markov Models**: 2-3 state Gaussian HMM using returns and range as features (via hmmlearn)
- **Hamilton regime-switching**: Markov regression with switching variance (via statsmodels)
- **GARCH models**: GJR-GARCH(1,1) with Student's t distribution for conditional volatility (via arch library)

Key implementation detail: Always use **filtered probabilities** (forward algorithm only) rather than Viterbi-decoded states to avoid look-ahead bias in real-time applications.

### Tier 3: Multi-Asset Turbulence (weekend build)
- **Kritzman & Li turbulence index**: Mahalanobis distance of cross-asset return vectors from historical distribution. Detects correlation breakdowns that VIX alone cannot capture.
- **Absorption ratio**: PCA-based measure of systemic fragility (fraction of variance in top 1/5 components)
- **Gaussian Mixture Models**: Unsupervised clustering of multi-dimensional features (returns, vol, range, VIX)

The turbulence index uses daily returns from: SPY, TLT, GLD, UUP, HYG, VIX level changes. Computed on rolling 252-day windows with inverse covariance matrix to detect correlation surprises.

### Composite Scoring
Combine five normalized (0-1) components:
- VIX percentile (25% weight)
- VIX term structure ratio (15% weight)
- Realized vol percentile (20% weight)
- Turbulence index percentile (25% weight)
- GARCH conditional vol percentile (15% weight)

Map composite score to regimes: 0-0.25 (low), 0.25-0.50 (normal), 0.50-0.75 (elevated), 0.75-1.0 (extreme).

## Python Environment

- Use virtual environment at `.venv` (user preference from global CLAUDE.md)
- Required core libraries: numpy, pandas, yfinance
- Tier 2 additions: hmmlearn, statsmodels, arch
- Tier 3 additions: scikit-learn, fredapi, frds (optional)
- Data APIs: polygon.io credentials in .env, FRED API key needed for fredapi

## Database

PostgreSQL database for storing:
- Historical price data (OHLC, volume)
- Computed volatility metrics
- Regime classifications and probabilities
- Composite turbulence scores

Connection parameters in .env: localhost:5432, database=postgres, credentials available.

## Critical Implementation Guidelines

### Avoiding Look-Ahead Bias
- **Never use full-sample statistics**: Always use rolling windows for means, covariances
- **HMM inference**: Use filtered probabilities (forward algorithm) NOT Viterbi decoding for real-time use
- **Walk-forward validation**: Train on 3-4 year window, test on next 6-12 months, slide forward
- **Rolling windows**: 252 days for annual statistics, 30 days for short-term vol, 500 days for absorption ratio

### Whipsaw Prevention
- **Hysteresis**: Different thresholds for entering vs exiting regimes (e.g., enter high-vol at VIX 28, exit at VIX 22)
- **Persistence filters**: Require regime to hold for 3-5 consecutive days before acting
- **Probabilistic sizing**: Use HMM filtered probabilities directly rather than hard regime labels

### Model Selection
- Compare models using BIC (Bayesian Information Criterion)
- For HMM: Test 2-5 components, sort states by covariance to label low vs high vol
- For GARCH: GJR-GARCH with Student's t typically wins for equity indices (~7-8 degrees of freedom)
- Retrain models monthly/quarterly on expanding windows

## Data Sources

Free data stack (sufficient for all tiers):
- **yfinance**: SPY, TLT, GLD, UUP, HYG, EFA, EEM, VNQ, ^VIX, ^VIX3M, ES=F
- **fredapi**: BAMLH0A0HYM2 (credit spreads), T10Y2Y (yield curve), DGS10, DGS2
- **Polygon.io**: 1-minute ES bars (credentials in .env)
- **Alpaca**: Free paper trading account with 10+ years intraday history

## Trading Applications

### ES Futures (support/resistance, order flow)
- **Position sizing**: Cut risk 25-50% when turbulence > 0.50, half size or stand aside when > 0.75
- **Stop widths**: Widen S/R zones by 1.5× ATR in high-vol regimes, expect level overshoot
- **Strategy selection**: S/R bounces in low-vol, momentum/breakout in high-vol, only major pivots in extreme

### Options
- **Low-vol regimes**: Buy cheap OTM puts, consider debit spreads
- **High-vol regimes**: Sell premium via credit spreads, jade lizards (90% of VIX > 30 spikes resolve in 3 months)
- **Extreme regimes**: Avoid naked short premium, use protective puts or defined-risk spreads

## Key References

Academic foundation:
- Kritzman & Li (2010) - Mahalanobis turbulence index
- Hamilton (1989) - Regime-switching framework
- Ang & Bekaert (2002, 2004) - Regime-based allocation
- Kritzman et al. (2011) - Absorption ratio

Notable repositories:
- bashtage/arch - GARCH models
- hmmlearn/hmmlearn - Gaussian HMM
- AI4Finance-Foundation/FinRL - Built-in turbulence index
- randlow/DM - All three Kritzman measures
- mgao6767/frds - Absorption ratio implementation

## Development Notes

- Build order: Tier 1 (VIX + Garman-Klass) → Tier 2 (GARCH + HMM) → Tier 3 (turbulence index + absorption ratio)
- Test each component independently before compositing
- Build Streamlit dashboard early to develop intuition before live trading
- Backtest red flags: returns > 12% annual, Sharpe > 1.5, suspiciously smooth equity curves
