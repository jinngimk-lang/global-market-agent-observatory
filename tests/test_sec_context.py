from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.intelligence.models import EvidenceKind


@pytest.fixture
def sec_payloads() -> dict[str, object]:
    return {
        "tickers": {
            "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
            "1": {"cik_str": 319201, "ticker": "KLAC", "title": "KLA CORP"},
        },
        "nvda": {
            "cik": "0001045810",
            "name": "NVIDIA CORP",
            "tickers": ["NVDA"],
            "filings": {
                "recent": {
                    "accessionNumber": [
                        "0001045810-26-000099",
                        "0001045810-26-000088",
                        "0001045810-26-000077",
                    ],
                    "filingDate": ["2026-08-26", "2026-08-20", "2026-08-01"],
                    "acceptanceDateTime": [
                        "2026-08-26T05:00:01.000Z",
                        "2026-08-20T21:30:02.000Z",
                        "2026-08-01T20:10:03.000Z",
                    ],
                    "form": ["8-K", "10-Q", "144"],
                    "primaryDocument": ["nvda-8k.htm", "nvda-10q.htm", "xsl144.xml"],
                    "primaryDocDescription": [
                        "Current Report",
                        "Quarterly Report",
                        "Form 144",
                    ],
                }
            },
        },
    }


def _client(sec_payloads: dict[str, object], *, now: datetime):
    from app.intelligence.sec import SecSubmissionClient

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "GlobalMarketAgent contact@example.com"
        if request.url.path == "/files/company_tickers.json":
            return httpx.Response(200, json=sec_payloads["tickers"])
        if request.url.path == "/submissions/CIK0001045810.json":
            return httpx.Response(200, json=sec_payloads["nvda"])
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return SecSubmissionClient(
        user_agent="GlobalMarketAgent contact@example.com",
        client=http_client,
        clock=lambda: now,
    ), http_client


@pytest.mark.asyncio
async def test_sec_client_normalizes_material_filings_from_official_submissions(
    sec_payloads,
) -> None:
    now = datetime(2026, 8, 26, 5, 0, 2, tzinfo=UTC)
    client, http_client = _client(sec_payloads, now=now)
    try:
        items = await client.fetch_recent("NVDA")
    finally:
        await http_client.aclose()

    assert [item.item_id for item in items] == [
        "sec:0001045810-26-000099",
        "sec:0001045810-26-000088",
    ]
    current = items[0]
    assert current.symbols == ["NVDA"]
    assert current.category == "filing"
    assert current.label == "SEC 8-K · Current Report"
    assert current.evidence_kind is EvidenceKind.FACT
    assert current.published_at.isoformat() == "2026-08-26T05:00:01+00:00"
    assert current.ingested_at == now
    assert current.provider_latency_seconds == 1
    assert current.freshness_sla_seconds == 120
    assert current.source.provider == "sec-edgar"
    assert current.source.official is True
    assert current.source.latency_class == "near-realtime"
    assert current.source.source_url == (
        "https://www.sec.gov/Archives/edgar/data/1045810/"
        "000104581026000099/nvda-8k.htm"
    )
    assert "form:8-K" in current.tags
    assert "cik:0001045810" in current.tags
    assert "company:NVIDIA CORP" in current.tags


@pytest.mark.asyncio
async def test_sec_client_uses_accession_as_delta_cursor(sec_payloads) -> None:
    now = datetime(2026, 8, 26, 5, 1, tzinfo=UTC)
    client, http_client = _client(sec_payloads, now=now)
    try:
        items = await client.fetch_recent(
            "NVDA", since_accession="0001045810-26-000088"
        )
    finally:
        await http_client.aclose()

    assert [item.item_id for item in items] == ["sec:0001045810-26-000099"]


@pytest.mark.asyncio
async def test_sec_client_caches_ticker_to_cik_mapping(sec_payloads) -> None:
    from app.intelligence.sec import SecSubmissionClient

    mapping_requests = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal mapping_requests
        if request.url.path == "/files/company_tickers.json":
            mapping_requests += 1
            return httpx.Response(200, json=sec_payloads["tickers"])
        if request.url.path == "/submissions/CIK0001045810.json":
            return httpx.Response(200, json=sec_payloads["nvda"])
        return httpx.Response(404)

    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = SecSubmissionClient(
        user_agent="GlobalMarketAgent contact@example.com", client=http_client
    )
    try:
        await client.fetch_recent("NVDA")
        await client.fetch_recent("NVDA")
    finally:
        await http_client.aclose()

    assert mapping_requests == 1


@pytest.mark.asyncio
async def test_sec_client_fails_closed_when_ticker_has_no_verified_cik(sec_payloads) -> None:
    now = datetime(2026, 8, 26, 5, 0, tzinfo=UTC)
    client, http_client = _client(sec_payloads, now=now)
    try:
        with pytest.raises(LookupError, match="CIK"):
            await client.fetch_recent("SPCX")
    finally:
        await http_client.aclose()


def test_sec_client_requires_declared_user_agent() -> None:
    from app.intelligence.sec import SecSubmissionClient

    with pytest.raises(ValueError, match="user_agent"):
        SecSubmissionClient(user_agent="")
