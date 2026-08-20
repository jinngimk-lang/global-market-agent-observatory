from __future__ import annotations

import json

import pytest

from app.market.alpaca import AlpacaStockBarFeed


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

    async def __aenter__(self) -> FakeWebSocket:
        return self.websocket

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_alpaca_stock_stream_authenticates_subscribes_and_normalizes_bar() -> None:
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"success","msg":"authenticated"}]',
            '[{"T":"subscription","bars":["KLAC","NVDA","SPCX"]}]',
            '[{"T":"b","S":"NVDA","o":200,"h":202,"l":199,"c":201.5,"v":12345,"t":"2026-08-20T13:40:00Z"}]',
        ]
    )
    feed = AlpacaStockBarFeed(
        symbols={"NVDA", "SPCX", "KLAC"},
        api_key="key",
        api_secret="secret",
        feed="iex",
        connect=lambda _: FakeConnection(websocket),
    )

    bars = [item async for item in feed.stream(limit=1)]

    assert websocket.sent == [
        {"action": "auth", "key": "key", "secret": "secret"},
        {"action": "subscribe", "bars": ["KLAC", "NVDA", "SPCX"]},
    ]
    assert len(bars) == 1
    assert bars[0].symbol == "NVDA"
    assert bars[0].open == 200
    assert bars[0].close == 201.5
    assert bars[0].volume == 12345
    assert bars[0].source == "alpaca:iex"
    assert bars[0].interval == "1m"
    assert bars[0].closed is True


@pytest.mark.asyncio
async def test_updated_bar_is_marked_as_market_revision_for_safe_upsert() -> None:
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"success","msg":"authenticated"}]',
            '[{"T":"subscription","bars":["NVDA"]}]',
            '[{"T":"u","S":"NVDA","o":200,"h":203,"l":199,"c":202,"v":13000,"t":"2026-08-20T13:40:00Z"}]',
        ]
    )
    feed = AlpacaStockBarFeed(
        symbols={"NVDA"},
        api_key="key",
        api_secret="secret",
        connect=lambda _: FakeConnection(websocket),
    )

    bars = [item async for item in feed.stream(limit=1)]

    assert bars[0].open_time.isoformat() == "2026-08-20T13:40:00+00:00"
    assert bars[0].close == 202
    assert bars[0].source == "alpaca:iex:updated"


@pytest.mark.asyncio
async def test_authentication_failure_fails_closed() -> None:
    websocket = FakeWebSocket(
        [
            '[{"T":"success","msg":"connected"}]',
            '[{"T":"error","code":402,"msg":"auth failed"}]',
        ]
    )
    feed = AlpacaStockBarFeed(
        symbols={"NVDA"},
        api_key="bad-key",
        api_secret="bad-secret",
        connect=lambda _: FakeConnection(websocket),
    )

    with pytest.raises(RuntimeError, match="authentication"):
        [item async for item in feed.stream(limit=1)]


def test_feed_requires_symbols_and_credentials() -> None:
    with pytest.raises(ValueError, match="symbol"):
        AlpacaStockBarFeed(symbols=set(), api_key="key", api_secret="secret")

    with pytest.raises(ValueError, match="credentials"):
        AlpacaStockBarFeed(symbols={"NVDA"}, api_key="", api_secret="")
