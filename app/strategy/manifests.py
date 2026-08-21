from __future__ import annotations

from app.innovation.models import StrategyHypothesis, StrategyStage


def strategy_hypotheses() -> dict[str, StrategyHypothesis]:
    """Canonical hypothesis manifests for currently enabled research strategies.

    Stage values describe evidence maturity, not broker capability. They are
    intentionally conservative until replay/paper evidence is persisted.
    """

    return {
        "vwap": StrategyHypothesis(
            strategy_id="vwap",
            version="1.0.0",
            problem=(
                "Identify selective intraday state transitions around an institutional "
                "volume-weighted reference without trading every observation."
            ),
            category_default=(
                "Treat price above/below VWAP as a generic directional bullish/bearish signal."
            ),
            deleted_constraint=(
                "VWAP must predict direction on every observation; the strategy may abstain "
                "until a directional state transition is observed."
            ),
            new_axis=(
                "Trade observable VWAP state transitions with explicit invalidation and make "
                "abstention quality a first-class outcome."
            ),
            expected_mechanism=(
                "A reclaim/rejection across the session volume-weighted reference is more "
                "specific than static location relative to VWAP and supplies a nearby invalidation."
            ),
            observable_inputs=["price", "volume", "session vwap"],
            provenance_requirements=[
                "timestamped normalized bars",
                "documented VWAP calculation window",
                "market-data source and revision status",
            ],
            falsification_conditions=[
                "out-of-sample expectancy is non-positive after costs",
                "transition signal does not outperform an equivalent random/naive crossing baseline",
            ],
            known_failure_regimes=[
                "illiquid or discontinuous markets",
                "stale/revised bars",
                "event gaps where VWAP invalidation understates risk",
            ],
            safety_constraints=[
                "stale market data blocks new risk",
                "portfolio and deterministic risk controls size every intent",
            ],
            stage=StrategyStage.REPLAY,
        ),
        "gamma-levels": StrategyHypothesis(
            strategy_id="gamma-levels",
            version="1.0.0",
            problem=(
                "Test whether transparent options-positioning reference levels become useful "
                "only when price interaction is confirmed by observable directional flow."
            ),
            category_default=(
                "Treat put wall and call wall estimates as authoritative support/resistance walls."
            ),
            deleted_constraint=(
                "A wall estimate alone is sufficient evidence for a trade; wall interaction "
                "must be confirmed by independently observed flow and explicit methodology."
            ),
            new_axis=(
                "Combine wall interaction with order-flow confirmation while retaining GEX sign, "
                "dealer-inventory assumptions, source provenance, and invalidation."
            ),
            expected_mechanism=(
                "If options-related hedging/liquidity effects matter, price behavior near a wall "
                "should be more informative when contemporaneous flow confirms defense or break."
            ),
            observable_inputs=[
                "underlying price",
                "options open interest",
                "option gamma/greeks",
                "order-flow imbalance",
            ],
            provenance_requirements=[
                "timestamped option chain and OI source",
                "documented GEX sign convention",
                "dealer-inventory assumption retained",
                "timestamped order-flow source",
            ],
            falsification_conditions=[
                "wall+flow events do not outperform wall-only or flow-only baselines out of sample",
                "results disappear after realistic chain latency/cost assumptions",
            ],
            known_failure_regimes=[
                "stale OI or Greeks",
                "incorrect dealer-position sign assumption",
                "thin option markets",
                "event gaps and expiration discontinuities",
            ],
            safety_constraints=[
                "wall estimates are labeled calculated/inferred rather than facts",
                "missing order flow produces HOLD rather than guessed confirmation",
                "stale chain or market state blocks new risk",
            ],
            stage=StrategyStage.REPLAY,
        ),
    }
