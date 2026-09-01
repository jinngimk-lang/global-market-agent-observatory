from __future__ import annotations

import pytest

from app.api.state import ApplicationState
from app.intelligence.government import FederalRegisterClient
from app.settings import Settings


def test_context_government_terms_are_configurable(monkeypatch) -> None:
    monkeypatch.setenv(
        "CONTEXT_GOVERNMENT_TERMS",
        "NVDA=NVIDIA|advanced computing;SPCX=SpaceX|Starlink",
    )

    settings = Settings.from_env()

    assert settings.context_government_terms == {
        "NVDA": ["NVIDIA", "advanced computing"],
        "SPCX": ["SpaceX", "Starlink"],
    }


@pytest.mark.asyncio
async def test_application_state_wires_federal_register_when_context_enabled(tmp_path) -> None:
    settings = Settings(
        database_path=str(tmp_path / "observatory.db"),
        context_intelligence_enabled=True,
    )
    state = ApplicationState(settings)

    try:
        assert isinstance(
            state.context_intelligence.government_client,
            FederalRegisterClient,
        )
        health = state.context_intelligence.source_health()["federal-register"]
        assert health.configured is True
    finally:
        await state.context_intelligence.stop()
