from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from app.intelligence.models import ContextItem, ContextSource, EvidenceKind

_MATERIAL_FORMS = {
    "6-K",
    "6-K/A",
    "8-K",
    "8-K/A",
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
}


class SecSubmissionClient:
    """Read official SEC submissions as near-real-time context facts."""

    def __init__(
        self,
        *,
        user_agent: str,
        client: httpx.AsyncClient | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        normalized_user_agent = user_agent.strip()
        if not normalized_user_agent:
            raise ValueError("user_agent is required for SEC requests")
        self._headers = {
            "User-Agent": normalized_user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(timeout=15.0)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ticker_map: dict[str, tuple[str, str]] | None = None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def fetch_recent(
        self,
        symbol: str,
        *,
        since_accession: str | None = None,
    ) -> list[ContextItem]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")
        cik, mapped_company = await self._resolve_cik(normalized_symbol)
        response = await self._client.get(
            f"https://data.sec.gov/submissions/CIK{cik}.json",
            headers=self._headers,
        )
        response.raise_for_status()
        payload = response.json()
        company = str(payload.get("name") or mapped_company).strip() or mapped_company
        recent = payload.get("filings", {}).get("recent", {})
        accessions = list(recent.get("accessionNumber", []))
        items: list[ContextItem] = []
        ingested_at = self._normalize_timestamp(self._clock())

        for index, accession_raw in enumerate(accessions):
            accession = str(accession_raw).strip()
            if not accession:
                continue
            if since_accession is not None and accession == since_accession:
                break

            form = str(self._value(recent, "form", index) or "").strip()
            if form not in _MATERIAL_FORMS:
                continue
            accepted_raw = str(
                self._value(recent, "acceptanceDateTime", index) or ""
            ).strip()
            if not accepted_raw:
                continue
            accepted_at = self._parse_timestamp(accepted_raw)
            primary_document = str(
                self._value(recent, "primaryDocument", index) or ""
            ).strip()
            description = str(
                self._value(recent, "primaryDocDescription", index) or ""
            ).strip()
            display_description = description or "Official filing"
            archive_url = self._archive_url(cik, accession, primary_document)

            items.append(
                ContextItem(
                    item_id=f"sec:{accession}",
                    symbols=[normalized_symbol],
                    category="filing",
                    label=f"SEC {form} · {display_description}",
                    summary=f"{company} filed {form}: {display_description}.",
                    event_time=accepted_at,
                    published_at=accepted_at,
                    ingested_at=ingested_at,
                    freshness_sla_seconds=120,
                    evidence_kind=EvidenceKind.FACT,
                    confidence="1",
                    tags=[
                        f"form:{form}",
                        f"cik:{cik}",
                        f"company:{company}",
                        f"accession:{accession}",
                    ],
                    source=ContextSource(
                        provider="sec-edgar",
                        source_type="filing",
                        official=True,
                        coverage="official company submissions",
                        latency_class="near-realtime",
                        source_url=archive_url,
                    ),
                )
            )
        return items

    async def _resolve_cik(self, symbol: str) -> tuple[str, str]:
        if self._ticker_map is None:
            response = await self._client.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=self._headers,
            )
            response.raise_for_status()
            payload = response.json()
            mapping: dict[str, tuple[str, str]] = {}
            if isinstance(payload, dict):
                for entry in payload.values():
                    if not isinstance(entry, dict):
                        continue
                    ticker = str(entry.get("ticker") or "").strip().upper()
                    title = str(entry.get("title") or "").strip()
                    cik_raw = entry.get("cik_str")
                    if not ticker or cik_raw is None:
                        continue
                    try:
                        cik = f"{int(cik_raw):010d}"
                    except (TypeError, ValueError):
                        continue
                    mapping[ticker] = (cik, title or ticker)
            self._ticker_map = mapping

        resolved = self._ticker_map.get(symbol)
        if resolved is None:
            raise LookupError(f"SEC CIK mapping not found for {symbol}")
        return resolved

    @staticmethod
    def _value(payload: dict[str, Any], key: str, index: int) -> Any | None:
        values = payload.get(key, [])
        if not isinstance(values, list) or index >= len(values):
            return None
        return values[index]

    @staticmethod
    def _archive_url(cik: str, accession: str, primary_document: str) -> str:
        numeric_cik = str(int(cik))
        accession_path = accession.replace("-", "")
        base = (
            f"https://www.sec.gov/Archives/edgar/data/{numeric_cik}/"
            f"{accession_path}"
        )
        return f"{base}/{primary_document}" if primary_document else base

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return SecSubmissionClient._normalize_timestamp(
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        )

    @staticmethod
    def _normalize_timestamp(value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
