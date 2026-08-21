# Innovation Doctrine for the Autonomous Trading Platform

## Purpose

This document adapts the project's innovation method to trading-system design.

The governing principle is **reframe before optimize**.

Do not begin by asking how to make an existing indicator, model, strategy, broker loop, or agent more accurate. First ask whether the default premise being optimized should exist at all.

The canonical reframing pattern is:

`old premise -> deleted constraint -> new axis`

A proposal is considered innovative only when it changes what the system competes on in a way that remains observable, falsifiable, operable, and safe.

## 1. Resolve the real job before the technique

Before adding a strategy or feature, identify:

- the real portfolio job-to-be-done;
- the failure or friction the current system experiences;
- the observable information available to solve it;
- the latency and provenance of that information;
- the risk if the hypothesis is wrong;
- the existing alternatives and workarounds;
- what a successful outcome looks like after transaction costs and operational failures.

A new indicator is not automatically a new capability. A strategy is useful only if removing it would remove a specific portfolio decision advantage.

## 2. Identify the category default

For each proposed capability, explicitly state the assumption conventional systems are mostly optimizing.

Examples in trading systems:

- more indicators produce better predictions;
- every signal should become a trade;
- the goal is to maximize backtest PnL;
- a support/resistance level is useful by itself;
- options OI reveals dealer positioning directly;
- a broker acknowledgement means execution state is known;
- the model should decide both opportunity and risk;
- cost basis should influence whether to add risk;
- automation means removing abstention and human-independent safety boundaries.

Then apply constraint deletion:

1. Why must this premise exist?
2. What if it disappears entirely?
3. What portfolio outcome remains after deleting it?
4. What new axis becomes important instead?

## 3. Explore three distinct directions before implementation

When a material feature or strategy is proposed, internally compare at least three approaches:

### A. Incremental improvement

Improve the current premise without changing it.

Examples: better VWAP parameters, more indicators, improved model calibration.

### B. Observable bridge

Connect the decision to a more direct observable market mechanism.

Examples: price crossing VWAP plus executed-flow confirmation; option wall interaction plus transparent GEX methodology; broker state plus reconciliation rather than inferred local state.

### C. Constraint-deletion reframe

Delete the premise the category is optimizing.

Examples:

- delete the requirement to predict direction on every bar -> optimize abstention quality and asymmetric setups;
- delete the assumption that a profitable in-sample backtest deserves capital -> optimize evidence promotion and survival out of sample;
- delete the assumption that one agent should decide everything -> optimize a deterministic safety kernel around replaceable hypotheses;
- delete the assumption that broker submit success equals known execution -> optimize reconciliation certainty before retry.

Do not implement the first plausible idea merely because it is familiar.

## 4. Project-specific reframes

### 4.1 Prediction-first -> state-transition-first

Old premise: the strategy should predict whether price will rise or fall.

Deleted constraint: every observation requires a directional forecast.

New axis: identify observable state transitions with asymmetric invalidation and abstain otherwise.

Implications:

- HOLD is a first-class output;
- invalidation quality matters as much as entry quality;
- strategies are evaluated on selective opportunity quality, not signal volume.

### 4.2 Indicator stack -> mechanism + provenance

Old premise: combining more indicators creates stronger conviction.

Deleted constraint: derived indicators can be treated as independent evidence.

New axis: prefer features tied to distinct observable mechanisms and retain their provenance/methodology.

Implications:

- VWAP, order flow, options positioning, off-exchange activity, and event risk keep separate provenance;
- correlated indicators must not masquerade as independent votes;
- inferred dealer positioning remains explicitly inferred.

### 4.3 Backtest winner -> evidence promotion

Old premise: the best historical PnL strategy should be deployed.

Deleted constraint: in-sample profitability is sufficient evidence.

New axis: promotion through reproducible evidence stages.

Canonical stages:

`idea -> research -> replay -> paper -> broker-paper -> live`

A strategy cannot skip stages merely because it is intuitively appealing or temporarily profitable.

### 4.4 Trade-every-signal -> abstention quality

Old premise: automation should maximize the number of decisions it executes.

Deleted constraint: a strategy signal must create market exposure.

New axis: only take risk when evidence, portfolio context, data freshness, and execution state all support the trade.

The system should be proud of correctly doing nothing.

### 4.5 Model authority -> deterministic safety kernel

Old premise: a sufficiently capable model should control opportunity, sizing, and execution.

Deleted constraint: intelligence and authority must be colocated.

New axis: replaceable strategy intelligence surrounded by deterministic risk, execution, reconciliation, audit, and kill-switch controls.

### 4.6 Submit-first -> broker-truth-first

Old premise: if the broker API accepted the request, the system can continue.

Deleted constraint: API response certainty is assumed.

New axis: broker reconciliation is the source of truth; unknown state freezes new risk until resolved.

### 4.7 Cost-basis recovery -> fresh-edge allocation

Old premise: a losing position becomes more attractive because its price is below the user's entry.

Deleted constraint: personal cost basis is a market signal.

New axis: every addition of risk requires a fresh, independently valid edge and portfolio approval.

## 5. Strategy Hypothesis Contract

Every material strategy should have a versioned hypothesis record containing:

- strategy id and version;
- portfolio problem being solved;
- category default;
- deleted constraint;
- new competition axis;
- observable inputs and their provenance requirements;
- expected mechanism;
- explicit falsification conditions;
- known failure regimes;
- safety constraints;
- current promotion stage;
- evidence references/metrics supporting the current stage.

The hypothesis record is not marketing. It is the compact explanation of why the strategy deserves continued testing.

## 6. Innovation Review Gate

Before a durable capability is accepted, score/review it against these dimensions:

1. **Problem specificity** — does it solve a concrete portfolio/system failure?
2. **Reframe clarity** — are the old premise, deleted constraint, and new axis explicit?
3. **Observable linkage** — is the mechanism connected to measurable market/broker data?
4. **Falsifiability** — can evidence prove the idea wrong?
5. **System specificity** — does it improve this architecture rather than being generic feature accumulation?
6. **Evidence safety** — are facts, calculated metrics, and assumptions kept distinct?
7. **Operational safety** — does failure remain bounded and fail closed?
8. **Simplicity** — is the additional complexity justified by measurable value?

Reject proposals that are merely:

- another indicator with no distinct mechanism;
- a named market concept with no reliable data source;
- a profitable backtest with no out-of-sample evidence;
- an LLM opinion that bypasses deterministic controls;
- a third-party metric whose methodology cannot be reconstructed;
- complexity that cannot be monitored or safely disabled.

## 7. Promotion Gate

Strategy promotion is separate from broker capability.

A broker adapter being technically capable of live orders does not make a strategy live-ready.

Default promotion sequence:

### Idea -> Research

Requires:

- explicit problem;
- category default;
- deleted constraint;
- new axis;
- falsification conditions.

### Research -> Replay

Requires:

- deterministic implementation;
- provenance for required inputs;
- replayable data path;
- transaction-cost assumptions documented.

### Replay -> Paper

Requires:

- out-of-sample or walk-forward evidence;
- enough independent observations for the claimed horizon;
- positive expectancy after modeled costs;
- bounded drawdown under policy;
- no unresolved look-ahead/data-leakage issue.

### Paper -> Broker Paper

Requires:

- paper execution evidence;
- idempotency/failure-injection tests;
- stale-data and outage behavior verified;
- operational metrics/audit complete.

### Broker Paper -> Live

Requires:

- broker-paper evidence;
- reconciliation verified under partial fills/cancel/restart/unknown outcomes;
- strategy degradation/disable rules defined;
- portfolio/group risk behavior verified;
- current strategy version explicitly approved for live.

Promotion must be version-specific. A material strategy change resets evidence to the appropriate earlier stage.

## 8. Persistent project protocol

Durable project truth must not depend on conversation memory.

Recovery order:

1. `PROJECT_DIRECTION.md`;
2. `STATUS.md`;
3. `AGENTS.md`;
4. this doctrine and active implementation skill(s);
5. newest relevant spec/plan/decision record;
6. current PR/CI/evidence state.

A durable new idea that survives review must update the appropriate canonical document and, when rationale would otherwise be lost, a decision record.

Do not silently stack contradictory rules. Replace obsolete assumptions deliberately and record what changed.

## 9. Decision record template for major innovations

Each durable reframe should capture:

- Context / problem
- Category default
- Deleted constraint
- New axis
- Alternatives explored
- Evidence required
- Safety impact
- Decision
- What old assumption this supersedes
- Revisit / falsification trigger

## 10. Current application

The first strategies governed by this doctrine are:

### VWAP v1

Old premise: relative position to VWAP is itself directional evidence.

Deleted constraint: VWAP must predict direction.

New axis: trade only an observable transition across VWAP with explicit invalidation; otherwise abstain.

### Gamma Levels v1

Old premise: put/call wall estimates act as authoritative support/resistance.

Deleted constraint: the wall estimate alone is enough.

New axis: require price interaction plus flow confirmation while retaining GEX sign/methodology assumptions.

Both remain research/replay hypotheses until evidence justifies promotion.
