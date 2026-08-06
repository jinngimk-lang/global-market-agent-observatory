from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.domain.models import EvidenceGrade


class DailyClose(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: datetime
    close: Decimal


class CrisisWindow(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    start: datetime
    end: datetime
    market: str
    max_drawdown: Decimal


class TradeCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    case_id: str
    actor_name: str
    actor_type: str
    instrument: str
    opened_at: datetime
    closed_at: datetime
    gross_pnl: Decimal
    costs: Decimal = Decimal("0")
    evidence_grade: EvidenceGrade
    evidence_urls: list[str] = Field(default_factory=list)
    strategy_tags: list[str] = Field(default_factory=list)
    notes: str = ""

    @computed_field
    @property
    def net_pnl(self) -> Decimal:
        return self.gross_pnl - self.costs


class CrisisWinner(BaseModel):
    model_config = ConfigDict(frozen=True)

    case: TradeCase
    window: CrisisWindow
    net_pnl: Decimal


def detect_crisis_windows(
    prices: list[DailyClose],
    *,
    drawdown_threshold: Decimal = Decimal("0.10"),
    market: str = "GLOBAL",
) -> list[CrisisWindow]:
    if not prices:
        return []
    if drawdown_threshold <= 0 or drawdown_threshold >= 1:
        raise ValueError("drawdown_threshold must be between 0 and 1")

    ordered = sorted(prices, key=lambda item: item.at)
    if any(item.close <= 0 for item in ordered):
        raise ValueError("close prices must be positive")

    windows: list[CrisisWindow] = []
    peak_price = ordered[0].close
    peak_at = ordered[0].at
    active_start: datetime | None = None
    active_peak = peak_price
    max_drawdown = Decimal("0")

    for point in ordered[1:]:
        if active_start is None:
            if point.close > peak_price:
                peak_price = point.close
                peak_at = point.at
                continue
            drawdown = point.close / peak_price - Decimal("1")
            if drawdown <= -drawdown_threshold:
                active_start = peak_at
                active_peak = peak_price
                max_drawdown = drawdown
            continue

        drawdown = point.close / active_peak - Decimal("1")
        max_drawdown = min(max_drawdown, drawdown)
        if point.close >= active_peak:
            windows.append(
                CrisisWindow(
                    name=f"drawdown-{active_start.date().isoformat()}",
                    start=active_start,
                    end=point.at,
                    market=market,
                    max_drawdown=max_drawdown,
                )
            )
            active_start = None
            peak_price = point.close
            peak_at = point.at
            max_drawdown = Decimal("0")

    if active_start is not None:
        windows.append(
            CrisisWindow(
                name=f"drawdown-{active_start.date().isoformat()}",
                start=active_start,
                end=ordered[-1].at,
                market=market,
                max_drawdown=max_drawdown,
            )
        )
    return windows


def find_verified_crisis_winners(
    cases: list[TradeCase], windows: list[CrisisWindow]
) -> list[CrisisWinner]:
    accepted_grades = {EvidenceGrade.A, EvidenceGrade.B}
    winners: list[CrisisWinner] = []
    for case in cases:
        if case.evidence_grade not in accepted_grades or case.net_pnl <= 0:
            continue
        if not case.evidence_urls:
            continue
        for window in windows:
            overlaps = case.opened_at <= window.end and case.closed_at >= window.start
            if overlaps:
                winners.append(CrisisWinner(case=case, window=window, net_pnl=case.net_pnl))
                break
    return sorted(winners, key=lambda item: item.net_pnl, reverse=True)
