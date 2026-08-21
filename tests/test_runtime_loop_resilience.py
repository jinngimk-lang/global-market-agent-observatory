from __future__ import annotations

import asyncio

import pytest

from app.api.state import ApplicationState
from app.settings import Settings


class UnusedOptionsSource:
    async def fetch_chain(self, *args, **kwargs):
        raise AssertionError("patched refresh should not call the options source")


@pytest.mark.asyncio
async def test_options_structure_loop_survives_unexpected_iteration_failure(
    tmp_path,
    monkeypatch,
) -> None:
    state = ApplicationState(
        Settings(
            database_path=str(tmp_path / "options-resilience.db"),
            strategy_learning_enabled=False,
            options_structure_enabled=True,
            options_structure_refresh_seconds=0.01,
        ),
        options_chain_source=UnusedOptionsSource(),
    )
    attempts = 0

    async def flaky_refresh(*, observed_at=None) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient options loop failure")

    monkeypatch.setattr(state, "refresh_options_structure_once", flaky_refresh)
    task = asyncio.create_task(state._run_options_structure())
    try:
        for _ in range(20):
            if attempts >= 2:
                break
            await asyncio.sleep(0.01)
    finally:
        if not task.done():
            task.cancel()
        try:
            await task
        except (asyncio.CancelledError, RuntimeError):
            pass

    assert attempts >= 2
    assert state.options_structure_loop_failure_count == 1
    assert state.last_options_structure_loop_error == (
        "RuntimeError: transient options loop failure"
    )
