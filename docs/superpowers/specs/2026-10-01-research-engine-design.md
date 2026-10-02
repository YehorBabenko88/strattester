# Strattester Research Engine Design

**Date:** 2026-10-01

## Purpose

Extend Strattester from an infrastructure/backtest scaffold into a causal research engine that can determine whether level, Smart Money Concepts (SMC), POC/volume-profile, and volatility-conditioned strategies show repeatable historical edge. Results must expose data completeness, market regime, instrument lifecycle, execution assumptions, and uncertainty rather than only aggregate PnL.

## Core research rule: no future information

Every derived market object has both `event_time` and `known_at`. A strategy may consume it only when `known_at <= decision_time`.

Examples:
- A completed 1H/4H/D/M high or low becomes usable only after that period closes.
- A swing high/low becomes usable only after the required right-side confirmation bars have closed.
- BOS/CHOCH and an order block become known only after their confirming structural event.
- A three-candle FVG becomes known only after the third candle closes.
- A rolling or session POC/VAH/VAL snapshot is frozen from data available before the decision.
- Volatility percentiles and regimes use only observations available before the decision.

Signals computed from a bar close cannot receive a market fill earlier than the next bar. Limit orders created by a close signal may fill from the next bar onward. If 1m OHLC cannot determine whether TP or SL occurred first, the baseline policy is conservative SL-first. A newly opened intrabar trade cannot also exit using an earlier part of that same bar.

## Historical data layer

The research engine must audit and expose, per symbol and time range:
- 1m OHLCV and turnover.
- Mark price, index price, premium index.
- Open interest and causal delta-OI.
- Funding.
- Long/short ratio.
- Historical public trades where available, including taker buy/sell volume, delta, turnover, trade count, trades/sec, VWAP, largest trade, and relative-volume features.

No unavailable historical L2/orderbook or liquidation stream may be fabricated. Strategies requiring genuine L2 are blocked for periods without captured L2.

POC has two explicit modes:
- `POC_PROXY`: approximation from candle data; never labelled as true traded-volume POC.
- `TRADE_POC`: volume profile constructed from historical public trades.

## Instrument lifecycle and universe

Maintain a lifecycle registry with `PRE_LISTING`, `ACTIVE`, `SUSPENDED`, and `DELISTED`. Store first/last seen, listing/delisting timestamps when known, and availability intervals.

A backtest at time T may only include instruments that were available at T. Delisted instruments remain in historical research. New listings have no synthetic pre-listing history and enter research only from actual available data.

Age cohorts are `0-7d`, `8-30d`, `31-90d`, and `90d+`.

Coverage is classified separately from lifecycle:
- `COMPLETE_HISTORY`: required range/datasets satisfy the strategy contract.
- `PARTIAL_HISTORY`: useful stored history exists but missing portions cannot currently be recovered.
- `INSUFFICIENT_HISTORY`: not enough data to execute the requested hypothesis.

Primary aggregate statistics use COMPLETE_HISTORY only. PARTIAL_HISTORY is researched and reported separately and can be compared with the complete cohort, but is never silently pooled into the primary aggregate.

Discovery of exchange instruments is periodic. A newly listed instrument creates prerequisite sync jobs. A disappeared instrument is not deleted; its status is reconciled and history retained.

## Strategy families

The engine treats each setup as a hypothesis, not as a guaranteed trading strategy.

### Levels
Test completed 1H, 4H, D, previous-day/session, monthly and yearly highs/lows; touch/rejection, breakout, breakout-retest, age, entry distance, direction, and confluence variants. Preserve the original 28 variants as regression baselines.

### SMC
Implement causal definitions for confirmed swing structure, BOS, CHOCH, liquidity sweep, order block, FVG, OB+FVG, sweep+BOS, and combinations with volume/trade delta/OI. Each definition is versioned and records the exact confirmation rule.

### POC / Volume Profile
Research previous-session/day/week and rolling 24h/72h/7d POC, VAH and VAL, POC migration and value-area width. Test mean reversion, breakout, retest, VAH/VAL rejection and confluence. Results always identify whether POC_PROXY or TRADE_POC was used.

### Volatility
Create a Volatility Observatory using causal ATR%, realized volatility, Parkinson range volatility, rolling high-low range, turnover/volume expansion, and percentile ranks relative to the instrument's own prior history. Produce `VERY_LOW`, `LOW`, `NORMAL`, `HIGH`, `EXTREME` regimes from versioned thresholds.

Every signal and every trade stores its volatility snapshot at decision/entry time. Reports work in both directions: strategy -> performance by volatility regime, and volatility regime -> comparison of strategy families.

### Controls and ablations
Compare complex hypotheses against simpler controls in the same time/liquidity/volatility cohort. Examples: OB vs OB+FVG vs OB+BOS vs OB+delta; level vs level+volume vs level+OI vs level+POC; SMC combinations vs simple momentum/reversal controls. This is required to distinguish incremental predictive value from generic momentum/volatility exposure.

## Execution and costs

Execution assumptions are versioned. Baseline retains $100 position size, 0.055% taker fee per side for the legacy regression contract, gap handling, next-bar causality, and conservative ambiguous-bar ordering. Research reports gross and net results separately. Slippage scenarios must be configurable and sensitivity-tested rather than assumed zero in the final comparison.

## Statistical evaluation

For each strategy/version/configuration preserve a trade journal and compute at minimum: trades, wins/losses, win rate, gross/net PnL, fees, expectancy, profit factor, max drawdown, MAE, MFE, R-multiple distribution, holding time, time in market, consecutive losses and tail-loss statistics.

Breakdowns include symbol, calendar period, lifecycle age cohort, liquidity cohort, trend regime, volatility regime, level/setup type, level/setup age, distance, and COMPLETE/PARTIAL coverage.

Validation is chronological. Use train/validation/test and walk-forward evaluation; never random train/test splitting for time-series strategy selection. Parameters selected on train/validation are frozen before test periods. Final untouched test statistics are distinct from exploratory statistics.

Run bootstrap confidence intervals for expectancy and related robust metrics and Monte Carlo/resampling of trade sequences for drawdown/losing-streak sensitivity. Multiple variants must retain the number of hypotheses tested so that selection bias is visible.

## Research outputs

Each run records strategy ID/version/fingerprint, feature-definition versions, dataset coverage, lifecycle status, POC mode, causal execution policy, fee/slippage assumptions, parameter source (fixed/train-selected), volatility snapshot/version, and code/data run identifiers.

Reports must make it impossible to confuse COMPLETE and PARTIAL history or in-sample and out-of-sample results.

## Integration

The research layer sits between historical stores and the existing strategy executor:

Historical stores -> Coverage/Lifecycle -> Causal Feature Engine -> Hypothesis Strategies -> Causal Execution -> Trade Journal -> Statistical Evaluator -> Walk-forward/Monte Carlo reports.

Scheduler prerequisites are generated from each strategy's dataset contract. Missing recoverable data schedules sync; unrecoverable delisted gaps yield PARTIAL_HISTORY; unavailable mandatory data yields INSUFFICIENT_HISTORY. Runtime data remains under C:\ProgramData\Strattester and outside immutable code releases.

## Testing requirements

Regression fixtures must prove known_at gating, next-bar execution, no synthetic pre-listing data, delisted retention, COMPLETE/PARTIAL separation, POC mode labelling, volatility snapshots using prior data only, and legacy 28-strategy semantics. Property-style tests should ensure adding future rows cannot alter signals/trades before those rows become known.
