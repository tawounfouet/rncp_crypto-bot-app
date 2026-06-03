"""Service de controle des bots Spot."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from mocks.scenarios import MockScenario
from schemas.bot import BotActionResult, BotInfo
from schemas.common import BotRuntimeStatus
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP


class BotControlService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def list_bots(self) -> list[BotInfo]:
        simulate_latency(self.store, min_ms=100, max_ms=300)
        raise_if_forced_error(self.store, "bots.list", "Erreur mock de listing bots.")
        bots = list(self.store.bots.values())
        if self.store.scenario == MockScenario.BOT_ERROR and bots:
            bots[0].status = BotRuntimeStatus.ERROR
            bots[0].last_action_result = "Perte de heartbeat detectee"
        if self.store.scenario == MockScenario.BOT_RUNNING:
            for bot in bots:
                if bot.status not in {BotRuntimeStatus.ERROR, BotRuntimeStatus.RUNNING}:
                    bot.status = BotRuntimeStatus.RUNNING
                    bot.last_action_result = "Execution continue"
        return sorted(bots, key=lambda bot: bot.name)

    def apply_action(self, bot_id: str, action: str) -> BotActionResult:
        simulate_latency(self.store, min_ms=180, max_ms=400)
        raise_if_forced_error(self.store, "bots.action", "Action bot refusee (mock).")
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        bot = self.store.bots.get(bot_id)
        if not bot:
            return BotActionResult(success=False, message="Bot introuvable.")

        now = datetime.now(UTC)
        if action == ACTION_START:
            if bot.status == BotRuntimeStatus.RUNNING:
                return BotActionResult(
                    success=False, message="Le bot est deja en execution.", bot=bot
                )
            bot.status = BotRuntimeStatus.RUNNING
            bot.last_action_result = "Demarrage mock confirme"
        elif action == ACTION_PAUSE:
            if bot.status not in {BotRuntimeStatus.RUNNING, BotRuntimeStatus.STARTING}:
                return BotActionResult(
                    success=False, message="Le bot ne peut pas etre mis en pause.", bot=bot
                )
            bot.status = BotRuntimeStatus.PAUSED
            bot.last_action_result = "Pause mock validee"
        elif action == ACTION_STOP:
            if bot.status == BotRuntimeStatus.STOPPED:
                return BotActionResult(success=False, message="Le bot est deja arrete.", bot=bot)
            bot.status = BotRuntimeStatus.STOPPED
            bot.last_action_result = "Arret mock securise"
        else:
            return BotActionResult(success=False, message="Action non supportee.", bot=bot)

        bot.last_action_at = now
        bot.heartbeat_at = now
        return BotActionResult(
            success=True,
            message=f"Action `{action}` appliquee sur {bot.name}.",
            bot=bot,
        )
