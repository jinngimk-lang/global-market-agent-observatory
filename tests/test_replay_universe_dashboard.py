from __future__ import annotations

from pathlib import Path

import pytest

from app.api.state import ApplicationState
from app.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
SWITCHER = ROOT / "app" / "web" / "symbol-switcher.js"


@pytest.mark.asyncio
async def test_replay_feed_covers_dashboard_universe_and_btc_reference(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "replay-universe.db"),
        market_source="replay",
        market_symbol="NVDA",
        trading_universe={"NVDA", "KLAC", "SPCX"},
        replay_delay_seconds=0,
        options_structure_enabled=False,
        strategy_learning_enabled=False,
    )
    state = ApplicationState(settings)

    assert state.feed.symbols == {"BTCUSDT", "NVDA", "KLAC", "SPCX"}

    candles = [candle async for candle in state.feed.stream(limit=4)]
    assert {candle.symbol for candle in candles} == {
        "BTCUSDT",
        "NVDA",
        "KLAC",
        "SPCX",
    }
    assert all(candle.source == "replay" for candle in candles)

    for candle in candles:
        await state.process_candle(candle)

    for symbol in {"BTCUSDT", "NVDA", "KLAC", "SPCX"}:
        assert state.store.latest_candle(symbol, interval="1m") is not None


def test_symbol_switcher_keeps_btc_visible_during_equity_replay() -> None:
    source = SWITCHER.read_text(encoding="utf-8")

    assert "marketSource === 'replay'" in source
    assert "['BTCUSDT']" in source
    assert "feedSymbols" in source
    assert "Replay Feed" in source
    assert "REPLAY 模拟" in source
