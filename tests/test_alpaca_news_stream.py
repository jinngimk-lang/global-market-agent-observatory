from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.intelligence.models import EvidenceKind


class FakeWebSocket:
    def __init__(self, messages: list[str]) -> None:
        self.messages = list(messages)
        self.sent: list[dict] = []

    async def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def recv(self) -> str:
        if not self.messages:
            raise AssertionError("Fake websocket ran out of messages")
        return self.messages.pop(0)


class FakeConnection:
    def __init__(self, websocket: FakeWebSocket) -> None:
        self.websocket = websocket
        self.exited = False
        self.exit_exception_type = None

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self.exited = True
        self.exit_exception_type = exc_type
        return None


def _news_module():
    from app.intelligence import alpaca_news

    return alpaca_news


@pytest.mark.asyncio
async def test_news_stream_authenticates_subscribes_and_normalizes_relevant_article() -> None:
    module = _news_module()
    ingested_at = datetime(2026, 8, 26, 5, 0, 2, tzinfo=UTC)
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"success","msg":"authenticated"}]',
            '[{"T":"subscription","news":["*"]}]',
            '[{"T":"n","id":40892639,"headline":"Nvidia supplier update","summary":"Fresh supplier news.","author":"Desk","created_at":"2026-08-26T05:00:00Z","updated_at":"2026-08-26T05:00:01Z","url":"https://example.com/story","content":"body","symbols":["NVDA","AMD"],"source":"benzinga"}]',
        ]
    )
    stream = module.AlpacaNewsStream(
        symbols={"NVDA", "KLAC", "SPCX"},
        api_key="key",
        api_secret="secret",
        connect=lambda _: FakeConnection(websocket),
        clock=lambda: ingested_at,
    )

    items = [item async for item in stream.stream(limit=1)]

    assert websocket.sent == [
        {"action": "auth", "key": "key", "secret": "secret"},
        {"action": "subscribe", "news": ["*"]},
    ]
    assert len(items) == 1
    item = items[0]
    assert item.item_id == "alpaca-news:40892639"
    assert item.symbols == ["NVDA"]
    assert item.category == "news"
    assert item.label == "Nvidia supplier update"
    assert item.summary == "Fresh supplier news."
    assert item.evidence_kind is EvidenceKind.FACT
    assert item.published_at.isoformat() == "2026-08-26T05:00:00+00:00"
    assert item.source_updated_at.isoformat() == "2026-08-26T05:00:01+00:00"
    assert item.event_time == item.source_updated_at
    assert item.ingested_at == ingested_at
    assert item.provider_latency_seconds == 1
    assert item.freshness_sla_seconds == 120
    assert item.source.provider == "alpaca-news"
    assert item.source.official is False
    assert item.source.coverage == "provider news tagged to configured symbols"
    assert item.source.source_url == "https://example.com/story"
    assert "publisher:benzinga" in item.tags
    assert "author:Desk" in item.tags


@pytest.mark.asyncio
async def test_news_stream_ignores_unrelated_symbols_and_non_news_frames() -> None:
    module = _news_module()
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"success","msg":"authenticated"}]',
            '[{"T":"subscription","news":["*"]}]',
            '[{"T":"success","msg":"heartbeat"}]',
            '[{"T":"n","id":1,"headline":"Apple only","summary":"Not relevant.","author":"Desk","created_at":"2026-08-26T05:00:00Z","updated_at":"2026-08-26T05:00:01Z","url":"https://example.com/aapl","symbols":["AAPL"],"source":"benzinga"}]',
            '[{"T":"n","id":2,"headline":"KLAC relevant","summary":"Relevant.","author":"Desk","created_at":"2026-08-26T05:00:02Z","updated_at":"2026-08-26T05:00:03Z","url":"https://example.com/klac","symbols":["KLAC"],"source":"benzinga"}]',
        ]
    )
    stream = module.AlpacaNewsStream(
        symbols={"NVDA", "KLAC", "SPCX"},
        api_key="key",
        api_secret="secret",
        connect=lambda _: FakeConnection(websocket),
        clock=lambda: datetime(2026, 8, 26, 5, 0, 4, tzinfo=UTC),
    )

    items = [item async for item in stream.stream(limit=1)]

    assert [item.item_id for item in items] == ["alpaca-news:2"]
    assert items[0].symbols == ["KLAC"]


@pytest.mark.asyncio
async def test_news_stream_authentication_failure_fails_closed_and_cleans_up() -> None:
    module = _news_module()
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"error","code":402,"msg":"auth failed"}]',
        ]
    )
    connection = FakeConnection(websocket)
    stream = module.AlpacaNewsStream(
        symbols={"NVDA"},
        api_key="bad-key",
        api_secret="bad-secret",
        connect=lambda _: connection,
    )

    with pytest.raises(RuntimeError, match="authentication"):
        [item async for item in stream.stream(limit=1)]

    assert connection.exited is True
    assert connection.exit_exception_type is RuntimeError


def test_news_stream_requires_symbols_and_credentials() -> None:
    module = _news_module()
    with pytest.raises(ValueError, match="symbol"):
        module.AlpacaNewsStream(symbols=set(), api_key="key", api_secret="secret")
    with pytest.raises(ValueError, match="credentials"):
        module.AlpacaNewsStream(symbols={"NVDA"}, api_key="", api_secret="")
