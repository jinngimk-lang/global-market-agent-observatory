from __future__ import annotations

import json

import httpx
import pytest


@pytest.mark.asyncio
async def test_historical_client_requests_provider_timeframe_and_preserves_coverage() -> None:
    from app.market.alpaca_history import AlpacaHistoricalBarsClient

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "bars": [
                    {
                        "t": "2026-08-27T04:00:00Z",
                        "o": 180.0,
                        "h": 184.0,
                        "l": 179.0,
                        "c": 183.0,
                        "v": 1234567,
                    }
                ],
                "symbol": "NVDA",
                "next_page_token": None,
            },
        )

    async with httpx.AsyncClient(
        base_url="https://data.alpaca.markets",
        transport=httpx.MockTransport(handler),
    ) as client:
        history = AlpacaHistoricalBarsClient(
            api_key="key",
            api_secret="secret",
            feed="iex",
            client=client,
        )
        result = await history.fetch("nvda", timeframe="1Day", limit=120)

    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == "/v2/stocks/NVDA/bars"
    assert request.url.params["timeframe"] == "1Day"
    assert request.url.params["feed"] == "iex"
    assert request.url.params["limit"] == "120"
    assert request.headers["APCA-API-KEY-ID"] == "key"
    assert request.headers["APCA-API-SECRET-KEY"] == "secret"

    assert result.symbol == "NVDA"
    assert result.timeframe == "1Day"
    assert result.feed == "iex"
    assert result.coverage == "single-exchange"
    assert len(result.candles) == 1
    assert result.candles[0].interval == "1d"
    assert result.candles[0].close == 183.0
    assert result.candles[0].source == "alpaca:iex:historical"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("timeframe", "interval"),
    [("1Day", "1d"), ("1Week", "1w"), ("1Month", "1mo")],
)
async def test_historical_client_supports_only_reviewed_dashboard_periods(
    timeframe: str,
    interval: str,
) -> None:
    from app.market.alpaca_history import AlpacaHistoricalBarsClient

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bars": [
                    {
                        "t": "2026-08-01T04:00:00Z",
                        "o": 100,
                        "h": 102,
                        "l": 99,
                        "c": 101,
                        "v": 1000,
                    }
                ],
                "next_page_token": None,
            },
        )

    async with httpx.AsyncClient(
        base_url="https://data.alpaca.markets",
        transport=httpx.MockTransport(handler),
    ) as client:
        history = AlpacaHistoricalBarsClient(
            api_key="key",
            api_secret="secret",
            feed="sip",
            client=client,
        )
        result = await history.fetch("KLAC", timeframe=timeframe, limit=20)

    assert result.candles[0].interval == interval
    assert result.coverage == "consolidated-us-market"


@pytest.mark.asyncio
async def test_historical_client_rejects_unreviewed_timeframe_before_http() -> None:
    from app.market.alpaca_history import AlpacaHistoricalBarsClient

    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"bars": []})

    async with httpx.AsyncClient(
        base_url="https://data.alpaca.markets",
        transport=httpx.MockTransport(handler),
    ) as client:
        history = AlpacaHistoricalBarsClient(
            api_key="key",
            api_secret="secret",
            client=client,
        )
        with pytest.raises(ValueError, match="timeframe"):
            await history.fetch("NVDA", timeframe="12Month", limit=20)

    assert calls == 0


@pytest.mark.asyncio
async def test_historical_client_fails_on_malformed_provider_payload_instead_of_faking_bars() -> None:
    from app.market.alpaca_history import AlpacaHistoricalBarsClient

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"bars": "not-a-list"}))

    async with httpx.AsyncClient(
        base_url="https://data.alpaca.markets",
        transport=httpx.MockTransport(handler),
    ) as client:
        history = AlpacaHistoricalBarsClient(
            api_key="key",
            api_secret="secret",
            client=client,
        )
        with pytest.raises(RuntimeError, match="bars payload"):
            await history.fetch("SPCX", timeframe="1Day", limit=20)
