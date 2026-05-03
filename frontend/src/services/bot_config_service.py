"""Service de configuration des bots."""

from __future__ import annotations

from datetime import datetime

from mocks.db import MockStore
from schemas.bot import BotConfig, BotConfigUpdate
from services.base import ServiceError, raise_if_forced_error, simulate_latency


class BotConfigService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def get_config(self, bot_id: str) -> BotConfig:
        simulate_latency(self.store, min_ms=90, max_ms=240)
        raise_if_forced_error(self.store, "bot_config.fetch", "Lecture config impossible (mock).")
        config = self.store.bot_configs.get(bot_id)
        if not config:
            raise ServiceError("Configuration bot introuvable.")
        return config

    def validate(self, update: BotConfigUpdate) -> list[str]:
        errors: list[str] = []
        if update.budget_usdt <= 0:
            errors.append("Le budget doit etre strictement positif.")
        if update.max_open_positions < 1:
            errors.append("Le nombre max de positions doit etre >= 1.")
        if not (0.1 <= update.risk_per_trade_pct <= 10):
            errors.append("Le risque par trade doit etre entre 0.1% et 10%.")
        if update.take_profit_pct <= 0:
            errors.append("Le take profit doit etre > 0.")
        if update.stop_loss_pct <= 0:
            errors.append("Le stop loss doit etre > 0.")
        if update.cooldown_seconds < 0:
            errors.append("Le cooldown ne peut pas etre negatif.")
        return errors

    def save(self, bot_id: str, update: BotConfigUpdate) -> tuple[bool, str, BotConfig | None]:
        simulate_latency(self.store, min_ms=140, max_ms=320)
        raise_if_forced_error(self.store, "bot_config.save", "Echec sauvegarde config (mock).")

        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        existing = self.store.bot_configs.get(bot_id)
        if not existing:
            return False, "Configuration introuvable.", None
        validation_errors = self.validate(update)
        if validation_errors:
            return False, " ; ".join(validation_errors), None

        new_config = existing.model_copy(
            update={
                "strategy": update.strategy,
                "budget_usdt": update.budget_usdt,
                "max_open_positions": update.max_open_positions,
                "risk_per_trade_pct": update.risk_per_trade_pct,
                "take_profit_pct": update.take_profit_pct,
                "stop_loss_pct": update.stop_loss_pct,
                "cooldown_seconds": update.cooldown_seconds,
                "version": existing.version + 1,
                "updated_at": datetime.utcnow(),
            }
        )
        self.store.bot_configs[bot_id] = new_config
        return True, "Configuration sauvegardee.", new_config
