from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.intelligence.government import FederalRegisterClient
from app.intelligence.models import EvidenceKind


def _client(payloads: dict[str, dict]) -> tuple[FederalRegisterClient, list[str]]:
    terms: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        term = request.url.params.get("conditions[term]") or ""
        terms.append(term)
        return httpx.Response(200, json=payloads.get(term, {"results": []}))

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return (
        FederalRegisterClient(
            symbol_terms={
                "NVDA": ["NVIDIA", "advanced computing semiconductors"],
                "KLAC": ["KLA Corporation", "semiconductor manufacturing equipment"],
            },
            client=http,
            clock=lambda: datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        ),
        terms,
    )


@pytest.mark.asyncio
async def test_unknown_symbol_is_not_silently_mapped_to_government_topics() -> None:
    client, _ = _client({})

    with pytest.raises(LookupError, match="government topic mapping"):
        await client.fetch_recent("SPCX")

    await client.close()


@pytest.mark.asyncio
async def test_fetch_recent_uses_only_explicit_symbol_terms_and_deduplicates_documents() -> None:
    document = {
        "document_number": "2026-18888",
        "title": "Export Controls on Advanced Computing Items",
        "abstract": "A rule concerning advanced computing semiconductor exports.",
        "type": "Rule",
        "publication_date": "2026-09-01",
        "effective_on": "2026-09-02",
        "html_url": "https://www.federalregister.gov/documents/2026/09/01/2026-18888/example",
        "agencies": [{"name": "Bureau of Industry and Security"}],
    }
    client, terms = _client(
        {
            "NVIDIA": {"results": [document]},
            "advanced computing semiconductors": {"results": [document]},
        }
    )

    items = await client.fetch_recent("nvda")

    assert terms == ["NVIDIA", "advanced computing semiconductors"]
    assert len(items) == 1
    assert items[0].item_id == "federal-register:2026-18888"
    assert items[0].symbols == ["NVDA"]
    await client.close()


@pytest.mark.asyncio
async def test_government_fact_preserves_publication_effective_date_and_legal_caveat() -> None:
    client, _ = _client(
        {
            "NVIDIA": {
                "results": [
                    {
                        "document_number": "2026-18888",
                        "title": "Export Controls on Advanced Computing Items",
                        "abstract": "A rule concerning advanced computing semiconductor exports.",
                        "type": "Rule",
                        "publication_date": "2026-09-01",
                        "effective_on": "2026-09-15",
                        "html_url": "https://www.federalregister.gov/documents/2026/09/01/2026-18888/example",
                        "agencies": [
                            {"name": "Bureau of Industry and Security"},
                            {"name": "Department of Commerce"},
                        ],
                    }
                ]
            }
        }
    )

    item = (await client.fetch_recent("NVDA"))[0]

    assert item.category == "government"
    assert item.evidence_kind is EvidenceKind.FACT
    assert item.event_time == datetime(2026, 9, 1, tzinfo=UTC)
    assert item.published_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert item.metadata["effective_on"] == "2026-09-15"
    assert item.metadata["document_type"] == "Rule"
    assert item.metadata["agencies"] == (
        "Bureau of Industry and Security; Department of Commerce"
    )
    assert item.metadata["legal_status"] == "verify-official-edition-on-govinfo"
    assert item.source.provider == "federal-register"
    assert item.source.official is True
    assert item.source.latency_class == "official-current"
    assert item.source.source_url.endswith("/example")
    assert item.freshness_sla_seconds == 86400
    await client.close()


@pytest.mark.asyncio
async def test_malformed_government_result_is_skipped_instead_of_fabricated() -> None:
    client, _ = _client(
        {
            "NVIDIA": {
                "results": [
                    {"title": "missing stable identity", "publication_date": "2026-09-01"},
                    {"document_number": "2026-1", "title": "missing publication date"},
                ]
            }
        }
    )

    assert await client.fetch_recent("NVDA") == []
    await client.close()
