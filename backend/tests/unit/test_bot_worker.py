"""Unit tests for bots.worker.BotWorker -- le code qui execute reellement les bots
en tache de fond en production (main.py, si ENABLE_BACKGROUND_TASKS), jusque-la sans
aucun test (0% de couverture)."""

from __future__ import annotations

import asyncio

import pytest


class _FakeService:
    def __init__(self, *, side_effects: list | None = None) -> None:
        self.calls: list[dict] = []
        self._side_effects = side_effects

    def execute_active_once(self, *, worker_id: str, limit: int):
        self.calls.append({"worker_id": worker_id, "limit": limit})
        if self._side_effects:
            effect = self._side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        return []


def test_run_once_delegates_to_service_with_worker_id_and_limit():
    from bots.worker import BotWorker

    service = _FakeService(side_effects=[["decision-1"]])
    worker = BotWorker(service=service, worker_id="test-worker")

    result = worker.run_once(limit=42)

    assert result == ["decision-1"]
    assert service.calls == [{"worker_id": "test-worker", "limit": 42}]


def test_run_once_uses_default_limit_of_100():
    from bots.worker import BotWorker

    service = _FakeService(side_effects=[[]])
    worker = BotWorker(service=service)

    worker.run_once()

    assert service.calls[0]["limit"] == 100


@pytest.mark.asyncio
async def test_run_forever_returns_immediately_if_stop_event_already_set():
    from bots.worker import BotWorker

    service = _FakeService()
    worker = BotWorker(service=service)
    stop_event = asyncio.Event()
    stop_event.set()

    await asyncio.wait_for(
        worker.run_forever(interval_seconds=1, stop_event=stop_event), timeout=2
    )

    assert service.calls == []


@pytest.mark.asyncio
async def test_run_forever_executes_at_least_one_pass_before_stopping():
    from bots.worker import BotWorker

    service = _FakeService(side_effects=[[]])
    worker = BotWorker(service=service)
    stop_event = asyncio.Event()

    async def _stop_after_first_pass():
        # Laisse une passe s'executer puis demande l'arret : run_forever doit
        # ressortir de son attente (asyncio.wait_for sur stop_event) sans relancer
        # de nouvelle passe.
        await asyncio.sleep(0.05)
        stop_event.set()

    stopper = asyncio.create_task(_stop_after_first_pass())
    await asyncio.wait_for(
        worker.run_forever(interval_seconds=60, stop_event=stop_event), timeout=2
    )
    await stopper

    assert len(service.calls) == 1


@pytest.mark.asyncio
async def test_run_forever_keeps_looping_when_a_pass_raises():
    from bots.worker import BotWorker

    # Une passe qui leve, suivie d'une passe normale : la boucle doit survivre a
    # l'exception (log + continue) plutot que de laisser le worker mourir. Le stop
    # est demande depuis l'interieur du fake (apres la 2e passe), pas par un minuteur
    # externe : entre deux passes, run_forever attend jusqu'a `interval` secondes ou
    # la mise a `set()` du stop_event, ce qui arrive en premier.
    stop_event = asyncio.Event()

    class _StoppingService(_FakeService):
        def execute_active_once(self, *, worker_id: str, limit: int):
            result = super().execute_active_once(worker_id=worker_id, limit=limit)
            if len(self.calls) >= 2:
                stop_event.set()
            return result

    service = _StoppingService(side_effects=[RuntimeError("boom"), []])
    worker = BotWorker(service=service)

    # interval_seconds est tronque via int() cote worker (max(int(x), 1)) : passer
    # une valeur < 1 ne l'accelere pas, on assume donc 1s reelle entre les passes.
    await asyncio.wait_for(
        worker.run_forever(interval_seconds=1, stop_event=stop_event), timeout=3
    )

    assert len(service.calls) == 2


@pytest.mark.asyncio
async def test_run_forever_logs_when_a_pass_returns_decisions(caplog):
    from bots.worker import BotWorker

    service = _FakeService(side_effects=[["decision-1", "decision-2"]])
    worker = BotWorker(service=service)
    stop_event = asyncio.Event()

    async def _stop_after_first_pass():
        await asyncio.sleep(0.05)
        stop_event.set()

    stopper = asyncio.create_task(_stop_after_first_pass())
    with caplog.at_level("INFO"):
        await asyncio.wait_for(
            worker.run_forever(interval_seconds=1, stop_event=stop_event), timeout=2
        )
    await stopper

    assert any("processed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_run_forever_without_stop_event_sleeps_between_passes_until_cancelled():
    from bots.worker import BotWorker

    # Sans stop_event (usage reel dans main.py : passe un stop_event, mais le
    # chemin `else: await asyncio.sleep(interval)` reste du code atteignable a
    # couvrir), la boucle ne s'arrete que par annulation externe de la tache.
    service = _FakeService(side_effects=[[], [], [], [], []])
    worker = BotWorker(service=service)

    task = asyncio.create_task(worker.run_forever(interval_seconds=1, stop_event=None))
    await asyncio.sleep(0.05)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(service.calls) >= 1


@pytest.mark.asyncio
async def test_run_forever_propagates_cancelled_error():
    from bots.worker import BotWorker

    class _CancellingService(_FakeService):
        def execute_active_once(self, *, worker_id: str, limit: int):
            raise asyncio.CancelledError

    worker = BotWorker(service=_CancellingService())

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(worker.run_forever(interval_seconds=1), timeout=2)
