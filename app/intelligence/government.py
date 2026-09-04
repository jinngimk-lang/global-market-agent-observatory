from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind


class FederalRegisterClient:
    """Read explicitly mapped Federal Register documents as official context.

    FederalRegister.gov metadata is useful for timely regulatory awareness, but
    it is not represented as the authoritative legal edition. Every normalized
    item therefore carries a GovInfo verification caveat in metadata.
    """

    def __init__(
        self,
        *,
        symbol_terms: dict[str, list[str]],
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._symbol_terms = {
            symbol.strip().upper(): [term.strip() for term in terms if term.strip()]
            for symbol, terms in symbol_terms.items()
            if symbol.strip()
        }
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=15.0)
        self._clock = clock or (lambda: datetime.now(UTC))

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_recent(self, symbol: str, *, limit: int = 20) -> list[ContextItem]:
        normalized = symbol.strip().upper()
        terms = self._symbol_terms.get(normalized)
        if not terms:
            raise LookupError(f"government topic mapping is unavailable for {normalized}")
        if limit <= 0:
            raise ValueError("limit must be positive")

        ingested_at = self._normalize_timestamp(self._clock())
        by_id: dict[str, ContextItem] = {}
        for term in terms:
            response = await self._client.get(
                "https://www.federalregister.gov/api/v1/documents.json",
                params={
                    "conditions[term]": term,
                    "per_page": min(limit, 100),
                    "order": "newest",
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                continue
            results = payload.get("results", [])
            if not isinstance(results, list):
                continue
            for raw in results:
                if not isinstance(raw, dict):
                    continue
                item = self._normalize_document(normalized, raw, ingested_at=ingested_at)
                if item is not None:
                    by_id[item.item_id] = item

        return sorted(
            by_id.values(),
            key=lambda item: (item.published_at, item.item_id),
            reverse=True,
        )[:limit]

    @classmethod
    def _normalize_document(
        cls,
        symbol: str,
        raw: dict[str, Any],
        *,
        ingested_at: datetime,
    ) -> ContextItem | None:
        document_number = str(raw.get("document_number") or "").strip()
        title = str(raw.get("title") or "").strip()
        publication_date = str(raw.get("publication_date") or "").strip()
        if not document_number or not title or not publication_date:
            return None
        try:
            published = cls._parse_date(publication_date)
        except ValueError:
            return None

        abstract = str(raw.get("abstract") or "").strip()
        document_type = str(raw.get("type") or "").strip() or "Federal Register document"
        effective_on = str(raw.get("effective_on") or "").strip()
        html_url = str(raw.get("html_url") or "").strip() or None
        agencies_raw = raw.get("agencies")
        agencies: list[str] = []
        if isinstance(agencies_raw, list):
            for agency in agencies_raw:
                if not isinstance(agency, dict):
                    continue
                name = str(agency.get("name") or "").strip()
                if name:
                    agencies.append(name)

        summary = abstract or f"{document_type} published in the Federal Register."
        return ContextItem(
            item_id=f"federal-register:{document_number}",
            symbols=[symbol],
            category="government",
            label=title,
            summary=summary,
            event_time=published,
            published_at=published,
            ingested_at=ingested_at,
            freshness_sla_seconds=86400,
            evidence_kind=EvidenceKind.FACT,
            tags=["government", "federal-register", document_type.lower()],
            metadata={
                "document_number": document_number,
                "document_type": document_type,
                "effective_on": effective_on,
                "agencies": "; ".join(agencies),
                "legal_status": "verify-official-edition-on-govinfo",
            },
            source=ContextSource(
                provider="federal-register",
                source_type="government-publication",
                official=True,
                coverage="us-federal-register-publications",
                latency_class="official-current",
                source_url=html_url,
            ),
        )

    @staticmethod
    def _parse_date(value: str) -> datetime:
        return datetime.fromisoformat(value).replace(tzinfo=UTC)

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
