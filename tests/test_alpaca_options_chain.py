from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from app.market.alpaca_options import AlpacaOptionsChainClient
from app.market.options import OptionRight


@pytest.mark.asyncio
async def test_alpaca_options_chain_merges_open_interest_and_greeks_with_provenance() -> None:
    def trading_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/options/contracts"
        assert request.url.params["underlying_symbols"] == "NVDA"
        assert request.url.params["status"] == "active"
        assert request.url.params["expiration_date_gte"] == "2026-08-21"
        assert request.url.params["expiration_date_lte"] == "2026-09-18"
        assert request.headers["APCA-API-KEY-ID"] == "key"
        return httpx.Response(
            200,
            json={
                "option_contracts": [
                    {
                        "symbol": "NVDA260918C00200000",
                        "underlying_symbol": "NVDA",
                        "type": "call",
                        "expiration_date": "2026-09-18",
                        "strike_price": "200",
                        "size": "100",
                        "open_interest": "1200",
                        "open_interest_date": "2026-08-20",
                    },
                    {
                        "symbol": "NVDA260918P00190000",
                        "underlying_symbol": "NVDA",
                        "type": "put",
                        "expiration_date": "2026-09-18",
                        "strike_price": "190",
                        "size": "100",
                        "open_interest": "1400",
                        "open_interest_date": "2026-08-20",
                    },
                ],
                "page_token": None,
            },
        )

    def data_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta1/options/snapshots/NVDA"
        assert request.url.params["feed"] == "indicative"
        assert request.url.params["expiration_date_gte"] == "2026-08-21"
        assert request.url.params["expiration_date_lte"] == "2026-09-18"
        assert request.headers["APCA-API-KEY-ID"] == "key"
        return httpx.Response(
            200,
            json={
                "snapshots": {
                    "NVDA260918C00200000": {
                        "impliedVolatility": 0.42,
                        "greeks": {"gamma": 0.018, "delta": 0.55},
                        "latestQuote": {"t": "2026-08-21T14:00:01Z"},
                    },
                    "NVDA260918P00190000": {
                        "impliedVolatility": 0.47,
                        "greeks": {"gamma": 0.021, "delta": -0.43},
                        "latestTrade": {"t": "2026-08-21T14:00:02Z"},
                    },
                },
                "next_page_token": None,
            },
        )

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(trading_handler),
            base_url="https://paper-api.alpaca.markets",
        ) as trading_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(data_handler),
            base_url="https://data.alpaca.markets",
        ) as data_client,
    ):
        client = AlpacaOptionsChainClient(
            api_key="key",
            api_secret="secret",
            trading_client=trading_client,
            data_client=data_client,
            feed="indicative",
        )
        chain = await client.fetch_chain(
            "NVDA",
            expiration_date_gte=date(2026, 8, 21),
            expiration_date_lte=date(2026, 9, 18),
            fetched_at=datetime(2026, 8, 21, 14, 0, 5, tzinfo=UTC),
        )

    assert chain.provider == "alpaca"
    assert chain.feed == "indicative"
    assert chain.underlying_symbol == "NVDA"
    assert chain.fetched_at == datetime(2026, 8, 21, 14, 0, 5, tzinfo=UTC)
    assert len(chain.contracts) == 2
    call = chain.contracts[0]
    assert call.contract_symbol == "NVDA260918C00200000"
    assert call.right is OptionRight.CALL
    assert call.strike == Decimal("200")
    assert call.open_interest == Decimal("1200")
    assert call.open_interest_date == date(2026, 8, 20)
    assert call.gamma == Decimal("0.018")
    assert call.implied_volatility == Decimal("0.42")
    assert call.market_data_updated_at == datetime(2026, 8, 21, 14, 0, 1, tzinfo=UTC)
    assert call.open_interest_source.endswith("/v2/options/contracts")
    assert call.greeks_source.endswith("/v1beta1/options/snapshots/NVDA")
    assert chain.gex_inputs()[1].open_interest == Decimal("1400")


@pytest.mark.asyncio
async def test_alpaca_options_chain_paginates_and_skips_incomplete_contracts() -> None:
    contract_pages: list[str | None] = []
    snapshot_pages: list[str | None] = []

    def trading_handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("page_token")
        contract_pages.append(token)
        if token is None:
            return httpx.Response(
                200,
                json={
                    "option_contracts": [
                        {
                            "symbol": "NVDA260918C00200000",
                            "underlying_symbol": "NVDA",
                            "type": "call",
                            "expiration_date": "2026-09-18",
                            "strike_price": "200",
                            "size": "100",
                            "open_interest": "100",
                            "open_interest_date": "2026-08-20",
                        }
                    ],
                    "page_token": "contracts-2",
                },
            )
        return httpx.Response(
            200,
            json={
                "option_contracts": [
                    {
                        "symbol": "NVDA260918P00190000",
                        "underlying_symbol": "NVDA",
                        "type": "put",
                        "expiration_date": "2026-09-18",
                        "strike_price": "190",
                        "size": "100",
                        "open_interest": None,
                        "open_interest_date": "2026-08-20",
                    }
                ],
                "page_token": None,
            },
        )

    def data_handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("page_token")
        snapshot_pages.append(token)
        if token is None:
            return httpx.Response(
                200,
                json={
                    "snapshots": {
                        "NVDA260918C00200000": {
                            "greeks": {"gamma": 0.02},
                            "latestQuote": {"t": "2026-08-21T14:00:01Z"},
                        }
                    },
                    "next_page_token": "snapshots-2",
                },
            )
        return httpx.Response(
            200,
            json={
                "snapshots": {
                    "NVDA260918P00190000": {
                        "greeks": None,
                        "latestQuote": {"t": "2026-08-21T14:00:02Z"},
                    }
                },
                "next_page_token": None,
            },
        )

    async with (
        httpx.AsyncClient(
            transport=httpx.MockTransport(trading_handler),
            base_url="https://paper-api.alpaca.markets",
        ) as trading_client,
        httpx.AsyncClient(
            transport=httpx.MockTransport(data_handler),
            base_url="https://data.alpaca.markets",
        ) as data_client,
    ):
        client = AlpacaOptionsChainClient(
            api_key="key",
            api_secret="secret",
            trading_client=trading_client,
            data_client=data_client,
        )
        chain = await client.fetch_chain(
            "NVDA",
            expiration_date_gte=date(2026, 8, 21),
            expiration_date_lte=date(2026, 9, 18),
        )

    assert contract_pages == [None, "contracts-2"]
    assert snapshot_pages == [None, "snapshots-2"]
    assert len(chain.contracts) == 1
    assert chain.skipped_missing_open_interest == 1
    assert chain.skipped_missing_gamma == 0
