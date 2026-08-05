"""Service de configuration des bots - connecte au backend reel (strategies)."""

from __future__ import annotations

from mocks.db import MockStore
from schemas.bot import BotConfig, BotConfigUpdate
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token
from utils.dates import parse_dt_or_now
from utils.numeric import to_float as _float
from utils.numeric import to_int as _int


def _extract_strategy(response_data: object) -> dict | None:
    if isinstance(response_data, dict):
        return response_data.get("data") or response_data
    return None


class BotConfigService:
    """
    Mappe les strategies backend aux BotConfig du frontend.
    Les parametres (budget, risque, etc.) sont stockes dans strategy.parameters.
    """

    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()

    def _token(self) -> str:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")
        return token

    def get_config(self, bot_id: str) -> BotConfig:
        token = self._token()
        response = self.client.get_strategy(token, bot_id)
        if not response.success:
            if response.status_code == 404:
                raise ServiceError(f"Strategie {bot_id[:12]}... introuvable.")
            raise ServiceError("Impossible de charger la configuration.")

        strategy = _extract_strategy(response.data)
        if not strategy:
            raise ServiceError("Reponse backend invalide.")

        params: dict = strategy.get("parameters") or {}
        symbol: str = params.get("symbol") or ""
        if len(symbol) > 4 and (symbol.endswith("USDT") or symbol.endswith("USDC")):
            base_asset = symbol[:-4]
        else:
            base_asset = params.get("base_asset") or "BTC"

        return BotConfig(
            bot_id=strategy.get("id", bot_id),
            version=_int(params.get("version"), 1),
            updated_at=parse_dt_or_now(strategy.get("updated_at")),
            strategy=strategy.get("strategy_type") or "custom",
            base_asset=base_asset,
            quote_asset=params.get("quote_asset") or "USDC",
            budget_usdt=_float(params.get("budget_usdt"), 1000.0),
            max_open_positions=_int(params.get("max_open_positions"), 3),
            risk_per_trade_pct=_float(params.get("risk_per_trade_pct"), 1.0),
            take_profit_pct=_float(params.get("take_profit_pct"), 3.0),
            stop_loss_pct=_float(params.get("stop_loss_pct"), 2.0),
            cooldown_seconds=_int(params.get("cooldown_seconds"), 300),
            enabled=bool(strategy.get("is_active", True)),
        )

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
        validation_errors = self.validate(update)
        if validation_errors:
            return False, " ; ".join(validation_errors), None

        token = self._token()

        # Recupere la config actuelle pour enrichir les parametres existants
        current_resp = self.client.get_strategy(token, bot_id)
        current_params: dict = {}
        current_version: int = 1
        if current_resp.success:
            s = _extract_strategy(current_resp.data)
            if s:
                current_params = dict(s.get("parameters") or {})
                current_version = _int(current_params.get("version"), 1)

        new_params = {
            **current_params,
            "budget_usdt": update.budget_usdt,
            "max_open_positions": update.max_open_positions,
            "risk_per_trade_pct": update.risk_per_trade_pct,
            "take_profit_pct": update.take_profit_pct,
            "stop_loss_pct": update.stop_loss_pct,
            "cooldown_seconds": update.cooldown_seconds,
            "version": current_version + 1,
        }

        payload = {"parameters": new_params, "strategy_type": update.strategy}
        response = self.client.update_strategy(token, bot_id, payload)
        if not response.success:
            if response.error:
                return False, response.error, None
            data = response.data
            if isinstance(data, dict):
                detail = data.get("detail")
                if isinstance(detail, str):
                    return False, detail, None
            return False, f"Erreur backend ({response.status_code}).", None

        updated_strategy = _extract_strategy(response.data)
        if not updated_strategy:
            return True, "Configuration sauvegardee.", None

        updated_params: dict = updated_strategy.get("parameters") or new_params
        symbol = updated_params.get("symbol") or ""
        if len(symbol) > 4 and (symbol.endswith("USDT") or symbol.endswith("USDC")):
            base_asset = symbol[:-4]
        else:
            base_asset = updated_params.get("base_asset") or "BTC"

        new_config = BotConfig(
            bot_id=bot_id,
            version=_int(updated_params.get("version"), current_version + 1),
            updated_at=parse_dt_or_now(updated_strategy.get("updated_at")),
            strategy=updated_strategy.get("strategy_type") or update.strategy,
            base_asset=base_asset,
            quote_asset=updated_params.get("quote_asset") or "USDC",
            budget_usdt=_float(updated_params.get("budget_usdt"), update.budget_usdt),
            max_open_positions=_int(
                updated_params.get("max_open_positions"), update.max_open_positions
            ),
            risk_per_trade_pct=_float(
                updated_params.get("risk_per_trade_pct"), update.risk_per_trade_pct
            ),
            take_profit_pct=_float(updated_params.get("take_profit_pct"), update.take_profit_pct),
            stop_loss_pct=_float(updated_params.get("stop_loss_pct"), update.stop_loss_pct),
            cooldown_seconds=_int(updated_params.get("cooldown_seconds"), update.cooldown_seconds),
        )
        return True, "Configuration sauvegardee.", new_config

    def create_bot(self, name, strategy_type):
        token = self._token()
        response = self.client.create_strategy(token, name=name, strategy_type=strategy_type)
        if not response.success:
            raise ServiceError("Impossible de créer une stratégie.")

    def get_available_models(self) -> list[dict]:
        token = self._token()
        response = self.client.get_available_models(token)
        if not response.success:
            raise ServiceError("Impossible de charger les modeles disponibles.")
        data = response.data
        if isinstance(data, dict):
            return data.get("data") or []
        return data if isinstance(data, list) else []
