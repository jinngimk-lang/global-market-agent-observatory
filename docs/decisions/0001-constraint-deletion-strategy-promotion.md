# Decision 0001 — Constraint Deletion and Strategy Promotion

Date: 2026-08-21
Status: Accepted

## Context

The project is becoming capable of autonomous broker execution. At the same time, market concepts such as VWAP, call/put walls, gamma exposure, order flow, dark-pool prints, and short-horizon effects can be easy to turn into attractive but weakly evidenced rules.

Technical ability to submit live orders must not be confused with evidence that a strategy deserves live capital.

## Category default

Conventional automated-trading development often optimizes this premise:

> discover/fit a promising strategy, backtest it, then wire it to execution.

This makes broker integration and backtest performance the implicit path to production.

## Deleted constraint

Delete the assumption that a strategy must progress toward live execution merely because it exists, sounds plausible, or produces profitable historical output.

## New axis

The system competes on **evidence promotion and safe abstention**:

- every strategy is a versioned hypothesis;
- every hypothesis states what premise it deletes and what mechanism replaces it;
- every material version progresses through explicit evidence stages;
- technical live capability and strategy live approval are independent gates;
- the system may remain fully operational while refusing to allocate live risk to unpromoted strategies.

## Alternatives explored

### Incremental improvement

Keep the existing strategy architecture and add more tests/backtests.

Rejected as insufficient because it does not create a durable barrier between promising research code and live autonomous execution.

### Observable bridge only

Require strategies to cite observable market mechanisms and provenance.

Adopted as necessary but insufficient because a well-sourced hypothesis may still lack out-of-sample and execution evidence.

### Constraint-deletion reframe

Separate strategy existence, broker capability, and live promotion into independent concerns.

Accepted.

## Decision

Adopt a versioned `StrategyHypothesis` model and deterministic `StrategyPromotionGate`.

Canonical stages:

`idea -> research -> replay -> paper -> broker-paper -> live`

Promotion is version-specific. Material strategy changes must return to the stage appropriate for the new uncertainty.

`ApplicationState` must eventually refuse autonomous execution in a mode above the promotion stage of any enabled strategy.

## Evidence required

Promotion policy will use recorded evidence such as:

- provenance completeness;
- replayability;
- transaction-cost assumptions;
- out-of-sample/walk-forward status;
- independent trade/observation count appropriate to the horizon;
- expectancy after modeled costs;
- drawdown;
- paper and broker-paper evidence;
- idempotency tests;
- failure injection;
- reconciliation under unknown/partial/cancel/restart states;
- strategy degradation/disable rules.

Thresholds are policy, not universal truths, and must be configurable and documented.

## Safety impact

This decision adds a new fail-closed layer between strategy logic and autonomous execution.

It does not replace deterministic portfolio/risk/execution controls. It prevents an unvalidated strategy version from reaching those controls in a higher-risk runtime mode.

## Superseded assumption

Supersedes the implicit assumption that implementing a strategy module is enough to make it eligible for any configured execution mode.

## Revisit / falsification trigger

Revisit if the promotion system becomes ceremonial rather than evidence-bearing, if stage thresholds encourage overfitting to the gate, or if different strategy horizons require substantially different promotion semantics. In that case, preserve the separation of strategy evidence from broker capability while revising the evidence policy.
