from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.market.options import OptionOpenInterestPoint, OptionRight


class OptionContractObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "alpaca"
    feed: str
    underlying_symbol: str
    contract_symbol: str
    right: OptionRight
    expiration_date: date
    strike: Decimal
    contract_multiplier: Decimal = Decimal("100")
    open_interest: Decimal
    open_interest_date: date
    gamma: Decimal
    implied_volatility: Decimal | None = None
    market_data_updated_at: datetime | None = None
    fetched_at: datetime
    open_interest_source: str
    greeks_source: str

    def gex_input(self) -> OptionOpenInterestPoint:
        return OptionOpenInterestPoint(
            strike=self.strike,
            right=self.right,
            open_interest=self.open_interest,
            gamma=self.gamma,
            contract_multiplier=self.contract_multiplier,
        )


class OptionChainObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str = "alpaca"
    feed: str
    underlying_symbol: str
    fetched_at: datetime
    contracts: list[OptionContractObservation] = Field(default_factory=list)
    skipped_missing_open_interest: int = 0
    skipped_missing_gamma: int = 0

    def gex_inputs(self) -> list[OptionOpenInterestPoint]:
        return [contract.gex_input() for contract in self.contracts]


class AlpacaOptionsChainClient:
    """Merge Alpaca contract OI metadata with option market-data Greeks.

    Open interest and Greeks come from different Alpaca API surfaces and can
    have different timestamps. This client deliberately keeps those origins
    separate so downstream GEX estimates can retain provenance.
    """

    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        trading_client: httpx.AsyncClient | None = None,
        data_client: httpx.AsyncClient | None = None,
        feed: str = "indicative",
    ) -> None:
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }
        self._owns_trading_client = trading_client is None
        self._owns_data_client = data_client is None
        self._trading_client = trading_client or httpx.AsyncClient(
            base_url="https://paper-api.alpaca.markets",
            timeout=20.0,
        )
        self._data_client = data_client or httpx.AsyncClient(
            base_url="https://data.alpaca.markets",
            timeout=20.0,
        )
        self.feed = feed.strip().lower()

    async def close(self) -> None:
        if self._owns_trading_client:
            await self._trading_client.aclose()
        if self._owns_data_client:
            await self._data_client.aclose()

    async def fetch_chain(
        self,
        underlying_symbol: str,
        *,
        expiration_date_gte: date,
        expiration_date_lte: date,
        fetched_at: datetime | None = None,
    ) -> OptionChainObservation:
        symbol = underlying_symbol.strip().upper()
        if not symbol:
            raise ValueError("underlying_symbol is required")
        if expiration_date_lte < expiration_date_gte:
            raise ValueError("expiration_date_lte must be >= expiration_date_gte")

        observed_at = fetched_at or datetime.now(UTC)
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)

        contracts = await self._fetch_contracts(
            symbol,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
        )
        snapshots = await self._fetch_snapshots(
            symbol,
            expiration_date_gte=expiration_date_gte,
            expiration_date_lte=expiration_date_lte,
        )

        oi_source = self._source_url(self._trading_client, "/v2/options/contracts")
        greeks_path = f"/v1beta1/options/snapshots/{symbol}"
        greeks_source = self._source_url(self._data_client, greeks_path)

        observations: list[OptionContractObservation] = []
        missing_oi = 0
        missing_gamma = 0
        for contract in contracts:
            open_interest = contract.get("open_interest")
            open_interest_date = contract.get("open_interest_date")
            if open_interest is None or open_interest_date in {None, ""}:
                missing_oi += 1
                continue

            contract_symbol = str(contract.get("symbol") or "").strip().upper()
            snapshot = snapshots.get(contract_symbol) or {}
            greeks = snapshot.get("greeks") or {}
            gamma = greeks.get("gamma")
            if gamma is None:
                missing_gamma += 1
                continue

            raw_right = str(contract.get("type") or "").strip().lower()
            if raw_right not in {OptionRight.CALL.value, OptionRight.PUT.value}:
                continue

            observations.append(
                OptionContractObservation(
                    feed=self.feed,
                    underlying_symbol=symbol,
                    contract_symbol=contract_symbol,
                    right=OptionRight(raw_right),
                    expiration_date=date.fromisoformat(str(contract["expiration_date"])),
                    strike=Decimal(str(contract["strike_price"])),
                    contract_multiplier=Decimal(str(contract.get("size") or "100")),
                    open_interest=Decimal(str(open_interest)),
                    open_interest_date=date.fromisoformat(str(open_interest_date)),
                    gamma=Decimal(str(gamma)),
                    implied_volatility=self._decimal_or_none(
                        snapshot.get("impliedVolatility")
                    ),
                    market_data_updated_at=self._latest_market_timestamp(snapshot),
                    fetched_at=observed_at,
                    open_interest_source=oi_source,
                    greeks_source=greeks_source,
                )
            )

        observations.sort(key=lambda item: (item.expiration_date, item.strike, item.right.value))
        return OptionChainObservation(
            feed=self.feed,
            underlying_symbol=symbol,
            fetched_at=observed_at,
            contracts=observations,
            skipped_missing_open_interest=missing_oi,
            skipped_missing_gamma=missing_gamma,
        )

    async def _fetch_contracts(
        self,
        symbol: str,
        *,
        expiration_date_gte: date,
        expiration_date_lte: date,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, str | int] = {
                "underlying_symbols": symbol,
                "status": "active",
                "expiration_date_gte": expiration_date_gte.isoformat(),
                "expiration_date_lte": expiration_date_lte.isoformat(),
                "limit": 10000,
            }
            if page_token:
                params["page_token"] = page_token
            response = await self._trading_client.get(
                "/v2/options/contracts",
                params=params,
                headers=self._headers,
            )
            response.raise_for_status()
            payload = response.json()
            items.extend(payload.get("option_contracts") or [])
            page_token = payload.get("next_page_token") or payload.get("page_token")
            if not page_token:
                return items

    async def _fetch_snapshots(
        self,
        symbol: str,
        *,
        expiration_date_gte: date,
        expiration_date_lte: date,
    ) -> dict[str, dict[str, Any]]:
        snapshots: dict[str, dict[str, Any]] = {}
        page_token: str | None = None
        path = f"/v1beta1/options/snapshots/{symbol}"
        while True:
            params: dict[str, str | int] = {
                "feed": self.feed,
                "expiration_date_gte": expiration_date_gte.isoformat(),
                "expiration_date_lte": expiration_date_lte.isoformat(),
                "limit": 1000,
            }
            if page_token:
                params["page_token"] = page_token
            response = await self._data_client.get(
                path,
                params=params,
                headers=self._headers,
            )
            response.raise_for_status()
            payload = response.json()
            snapshots.update(payload.get("snapshots") or {})
            page_token = payload.get("next_page_token") or payload.get("page_token")
            if not page_token:
                return snapshots

    @staticmethod
    def _decimal_or_none(value: Any) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(value))

    @classmethod
    def _latest_market_timestamp(cls, snapshot: dict[str, Any]) -> datetime | None:
        candidates: list[datetime] = []
        for key in ("latestQuote", "latestTrade"):
            raw = (snapshot.get(key) or {}).get("t")
            if raw:
                parsed = cls._parse_datetime(str(raw))
                if parsed is not None:
                    candidates.append(parsed)
        return max(candidates) if candidates else None

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        normalized = value.strip().replace("Z", "+00:00")
        if not normalized:
            return None
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    @staticmethod
    def _source_url(client: httpx.AsyncClient, path: str) -> str:
        return f"{str(client.base_url).rstrip('/')}{path}"
