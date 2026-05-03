from __future__ import annotations

from schemas.common import BotRuntimeStatus
from services.bot_control_service import BotControlService
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP


def test_list_bots(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotControlService(store)
    bots = service.list_bots()
    assert len(bots) >= 2


def test_bot_transitions(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotControlService(store)

    bot_id = "bot_sol_trend"
    start_result = service.apply_action(bot_id, ACTION_START)
    assert start_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.RUNNING

    pause_result = service.apply_action(bot_id, ACTION_PAUSE)
    assert pause_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.PAUSED

    stop_result = service.apply_action(bot_id, ACTION_STOP)
    assert stop_result.success is True
    assert store.bots[bot_id].status == BotRuntimeStatus.STOPPED
