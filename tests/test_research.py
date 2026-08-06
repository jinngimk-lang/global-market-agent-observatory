from datetime import UTC, datetime

import httpx
import pytest

from app.domain.models import EvidenceGrade
from app.research.evidence import grade_evidence
from app.research.github_releases import GitHubReleaseCollector
from app.research.sec import parse_sec_submissions


def sec_payload() -> dict:
    return {
        "cik": "320193",
        "name": "Example Global Inc.",
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-25-000001", "0000320193-22-000001"],
                "filingDate": ["2025-05-01", "2022-05-01"],
                "reportDate": ["2025-04-30", "2022-04-30"],
                "acceptanceDateTime": ["2025-05-01T12:00:00.000Z", "2022-05-01T12:00:00.000Z"],
                "form": ["8-K", "8-K"],
                "items": ["1.01,9.01", "1.01"],
                "primaryDocument": ["material-agreement.htm", "old-agreement.htm"],
                "primaryDocDescription": [
                    "Entry into a Material Definitive Agreement",
                    "Old agreement",
                ],
            }
        },
    }


def test_evidence_grading_is_fail_closed() -> None:
    assert grade_evidence("broker_export") is EvidenceGrade.A
    assert grade_evidence("regulator_filing") is EvidenceGrade.B
    assert grade_evidence("company_release") is EvidenceGrade.C
    assert grade_evidence("social_media_screenshot") is EvidenceGrade.D
    assert grade_evidence("unknown") is EvidenceGrade.D


def test_sec_parser_keeps_recent_material_agreements_only() -> None:
    observed_at = datetime(2026, 8, 6, tzinfo=UTC)

    items = parse_sec_submissions(sec_payload(), observed_at=observed_at, years=3)

    assert len(items) == 1
    item = items[0]
    assert item.grade is EvidenceGrade.B
    assert item.entity == "Example Global Inc."
    assert item.event_date == datetime(2025, 5, 1, tzinfo=UTC)
    assert "partnership" in item.tags
    assert item.source_url.endswith("/000032019325000001/material-agreement.htm")
    assert len(item.content_hash) == 64


@pytest.mark.asyncio
async def test_github_release_collector_uses_official_release_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/ccxt/ccxt/releases/latest"
        return httpx.Response(
            200,
            json={
                "id": 123,
                "name": "v5.0.0",
                "tag_name": "v5.0.0",
                "html_url": "https://github.com/ccxt/ccxt/releases/tag/v5.0.0",
                "published_at": "2026-08-01T00:00:00Z",
                "body": "Breaking API changes and exchange updates.",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    ) as client:
        collector = GitHubReleaseCollector(client=client)
        items = await collector.collect(["ccxt/ccxt"])

    assert len(items) == 1
    assert items[0].grade is EvidenceGrade.C
    assert items[0].entity == "ccxt/ccxt"
    assert items[0].tags == ["software-release"]
