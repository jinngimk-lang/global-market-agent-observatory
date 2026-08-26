from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class EvidenceKind(StrEnum):
    FACT = "fact"
    DERIVED = "derived"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class FreshnessClass(StrEnum):
    REALTIME = "realtime"
    NEAR_REALTIME = "near-realtime"
    OFFICIAL_CURRENT = "official-current"
    DELAYED = "delayed"
    STALE = "stale"
    UNKNOWN = "unknown"


class ContextSource(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    source_type: str
    official: bool = False
    coverage: str
    latency_class: str = "realtime"
    source_url: str | None = None

    @field_validator("provider", "source_type", "coverage", "latency_class")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("context source fields must not be empty")
        return normalized


class ContextItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: str
    symbols: list[str] = Field(default_factory=list)
    category: str
    label: str
    summary: str
    event_time: datetime
    published_at: datetime
    source_updated_at: datetime | None = None
    ingested_at: datetime
    freshness_sla_seconds: int
    evidence_kind: EvidenceKind
    confidence: Decimal = Decimal("1")
    tags: list[str] = Field(default_factory=list)
    source: ContextSource

    @field_validator("item_id", "category", "label", "summary")
    @classmethod
    def required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("context item text fields must not be empty")
        return normalized

    @field_validator("symbols")
    @classmethod
    def normalize_symbols(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip().upper() for item in value if item.strip()))

    @field_validator("event_time", "published_at", "source_updated_at", "ingested_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("freshness_sla_seconds")
    @classmethod
    def positive_sla(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("freshness_sla_seconds must be positive")
        return value

    @field_validator("confidence")
    @classmethod
    def bounded_confidence(cls, value: Decimal) -> Decimal:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value

    @computed_field
    @property
    def provider_latency_seconds(self) -> Decimal:
        provider_time = self.source_updated_at or self.published_at
        seconds = (self.ingested_at - provider_time).total_seconds()
        return Decimal(str(max(seconds, 0.0)))

    @computed_field
    @property
    def clock_anomaly(self) -> bool:
        provider_time = self.source_updated_at or self.published_at
        return provider_time > self.ingested_at


class SymbolContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    symbol: str
    generated_at: datetime
    news: list[ContextItem] = Field(default_factory=list)
    filings: list[ContextItem] = Field(default_factory=list)
    government: list[ContextItem] = Field(default_factory=list)
    flow: list[ContextItem] = Field(default_factory=list)
    synthesis: str = "NO VERIFIED DATA"
    synthesis_confidence: Decimal | None = None
    aggregate_flags: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must not be empty")
        return normalized

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
