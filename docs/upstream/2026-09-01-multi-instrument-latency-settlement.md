# Multi-instrument latency settlement correctness

## Upstream evidence

- Upstream: `nautechsystems/nautilus_trader`
- Commit: `673f30ae5beaedc1b7f37b36830e4176de8b5610`
- Date: 2026-09-01
- Issue: `nautechsystems/nautilus_trader#4891`
- License: LGPL-3.0
- Reuse mode: behavior/principle only; no upstream source copied.

The upstream regression showed that a latency-aware multi-instrument backtest could fill a MARKET order for one instrument against the wrong bar depending only on the registration/order of an unrelated second instrument. The fix scopes delayed-command settlement to matching instrument data while preserving unrestricted settlement for timer, funding, streaming-finalization, and shutdown paths.

## Local relevance

The current project does not yet simulate broker/order latency as a delayed command queue in replay. Strategy learning currently models transaction costs and entry/exit slippage, and records observed broker-fill latency when an exact authoritative fill exists, but modeled replay entries are not delayed through an execution-latency engine. Therefore the exact NautilusTrader defect is not presently reproducible in this repository and no production/backtest code is changed by this intake.

The upstream failure is nevertheless a durable validation constraint for future latency simulation because this project is explicitly multi-symbol. Adding a latency model must not make an instrument's fill price or settlement timing depend on unrelated instrument registration order or unrelated market-data arrival.

## Required future invariants

If modeled execution latency is added to replay/walk-forward/OOS evaluation:

1. delayed order commands must remain bound to the target symbol/instrument identity;
2. unrelated-symbol data must not make a delayed command eligible for execution;
3. fills for a symbol must be invariant to registration/order of unrelated symbols when the target symbol's data and signal stream are unchanged;
4. timer/funding/end-of-stream/shutdown settlement must use explicitly defined cross-instrument semantics rather than accidentally inheriting per-symbol gating;
5. modeled latency must be calibrated from observed broker-paper/live execution evidence where possible, and provenance must distinguish modeled from observed latency;
6. multi-symbol permutation tests must be part of RED/GREEN verification before latency-aware replay can contribute to strategy-promotion evidence.

## Adoption decision

Record the mechanism and future regression contract now; do not add a latency engine merely to mirror upstream. Implementation becomes justified only when this repository introduces modeled order latency or a local RED demonstrates order-settlement coupling across symbols. This keeps dependency/runtime cost at zero and rollback is deletion of this provenance note only.
