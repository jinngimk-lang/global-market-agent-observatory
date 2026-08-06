from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.domain.models import EvidenceItem
from app.research.evidence import content_hash, grade_evidence

_MATERIAL_FORMS = {"8-K", "8-K/A", "6-K", "6-K/A"}
_PARTNERSHIP_KEYWORDS = {
    "agreement",
    "partnership",
    "collaboration",
    "strategic alliance",
    "joint venture",
    "supply",
    "investment",
    "acquisition",
}


def _cutoff(observed_at: datetime, years: int) -> datetime:
    try:
        return observed_at.replace(year=observed_at.year - years)
    except ValueError:
        return observed_at.replace(month=2, day=28, year=observed_at.year - years)


def _value_at(columns: dict[str, list[Any]], key: str, index: int, default: Any = "") -> Any:
    values = columns.get(key, [])
    return values[index] if index < len(values) else default


def parse_sec_submissions(
    payload: dict[str, Any], *, observed_at: datetime, years: int = 3
) -> list[EvidenceItem]:
    observed_at = observed_at.astimezone(UTC)
    cutoff = _cutoff(observed_at, years)
    cik = str(payload.get("cik", "")).lstrip("0") or "0"
    entity = str(payload.get("name") or f"CIK {cik}")
    columns = payload.get("filings", {}).get("recent", {})
    accession_numbers = columns.get("accessionNumber", [])
    items: list[EvidenceItem] = []

    for index, accession in enumerate(accession_numbers):
        filing_date_raw = str(_value_at(columns, "filingDate", index))
        try:
            filing_date = datetime.fromisoformat(filing_date_raw).replace(tzinfo=UTC)
        except ValueError:
            continue
        if filing_date < cutoff:
            continue

        form = str(_value_at(columns, "form", index)).upper()
        if form not in _MATERIAL_FORMS:
            continue

        filing_items = str(_value_at(columns, "items", index))
        primary_document = str(_value_at(columns, "primaryDocument", index))
        description = str(_value_at(columns, "primaryDocDescription", index))
        searchable = " ".join((filing_items, primary_document, description)).lower()
        is_material_agreement = "1.01" in filing_items or any(
            keyword in searchable for keyword in _PARTNERSHIP_KEYWORDS
        )
        if not is_material_agreement:
            continue

        accession_compact = str(accession).replace("-", "")
        source_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_compact}/"
            f"{primary_document}"
        )
        raw_identity = {
            "cik": cik,
            "accession": accession,
            "filing_date": filing_date_raw,
            "form": form,
            "items": filing_items,
            "primary_document": primary_document,
            "description": description,
        }
        tags = ["partnership", "material-agreement"]
        items.append(
            EvidenceItem(
                evidence_id=f"sec-{accession_compact}",
                title=f"{entity} {form} material agreement",
                source_type="regulator_filing",
                source_url=source_url,
                grade=grade_evidence("regulator_filing"),
                observed_at=observed_at,
                event_date=filing_date,
                entity=entity,
                summary=description or f"{form} filing with item {filing_items}.",
                content_hash=content_hash(raw_identity),
                tags=tags,
                metadata={
                    "cik": cik,
                    "accession_number": str(accession),
                    "form": form,
                    "items": filing_items,
                },
            )
        )
    return items


class SECCollector:
    def __init__(self, *, user_agent: str, client: httpx.AsyncClient | None = None) -> None:
        if "@" not in user_agent:
            raise ValueError("SEC user agent must include a contact email address")
        self._client = client
        self._headers = {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}

    async def collect_company(
        self, cik: str, *, observed_at: datetime | None = None, years: int = 3
    ) -> list[EvidenceItem]:
        normalized_cik = str(cik).zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{normalized_cik}.json"
        observed_at = observed_at or datetime.now(UTC)
        if self._client is not None:
            response = await self._client.get(url, headers=self._headers)
            response.raise_for_status()
            return parse_sec_submissions(response.json(), observed_at=observed_at, years=years)

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(url, headers=self._headers)
            response.raise_for_status()
            return parse_sec_submissions(response.json(), observed_at=observed_at, years=years)
