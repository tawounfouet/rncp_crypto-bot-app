"""Service de controle des bots Spot - connecte au backend reel (strategies/deployments)."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.bot import BotActionResult, BotInfo
from schemas.common import BotRuntimeStatus
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token
from utils.constants import ACTION_START, ACTION_STOP

_DEPLOY_STATUS_MAP: dict[str, BotRuntimeStatus] = {
    "active": BotRuntimeStatus.RUNNING,
    "paused": BotRuntimeStatus.PAUSED,
    "stopped": BotRuntimeStatus.STOPPED,
    "error": BotRuntimeStatus.ERROR,
}


def _parse_dt(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(UTC)


class BotControlService:
    """
    Mappe les strategies (+ leurs deployments actifs) aux BotInfo du frontend.
    Un deployment actif = bot en cours d'execution.
    bot.id = strategy.id (utilise aussi dans BotConfigService).
    """

    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()
        # deployment_id par strategy_id (pour l'action STOP)
        self._active_deployments: dict[str, str] = {}

    def _token(self) -> str:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")
        return token

    def list_bots(self) -> list[BotInfo]:
        token = self._token()

        # Recupere la liste des strategies
        strat_resp = self.client.list_strategies(token)
        if not strat_resp.success:
            raise ServiceError("Impossible de charger les strategies.")

        raw_strategies = []
        data = strat_resp.data
        if isinstance(data, dict):
            raw_strategies = data.get("data") or data.get("strategies") or []
        elif isinstance(data, list):
            raw_strategies = data

        # Recupere les deployments actifs
        deploy_resp = self.client.list_deployments(token, active_only=True)
        active_by_strategy: dict[str, dict] = {}
        if deploy_resp.success:
            raw_deploys = []
            dd = deploy_resp.data
            if isinstance(dd, dict):
                raw_deploys = dd.get("data") or dd.get("deployments") or []
            elif isinstance(dd, list):
                raw_deploys = dd
            for d in raw_deploys:
                sid = d.get("strategy_id", "")
                if sid and d.get("status") == "active":
                    active_by_strategy[sid] = d

        self._active_deployments = {sid: d["id"] for sid, d in active_by_strategy.items()}

        bots: list[BotInfo] = []
        now = datetime.now(UTC)
        for s in raw_strategies:
            sid = s.get("id", "")
            deployment = active_by_strategy.get(sid)
            if deployment:
                status = _DEPLOY_STATUS_MAP.get(
                    deployment.get("status", "stopped"), BotRuntimeStatus.STOPPED
                )
                heartbeat = _parse_dt(deployment.get("updated_at"))
            else:
                # Cherche le dernier deployment (pas forcement actif)
                status = BotRuntimeStatus.STOPPED
                heartbeat = _parse_dt(s.get("updated_at"))

            bots.append(
                BotInfo(
                    id=sid,
                    name=s.get("name") or sid[:12],
                    strategy=s.get("strategy_type") or "custom",
                    mode_live=True,
                    status=status,
                    heartbeat_at=heartbeat or now,
                    last_action_result="",
                    last_action_at=heartbeat or now,
                )
            )

        return sorted(bots, key=lambda b: b.name)

    def create_bot(
        self,
        name: str,
        strategy_type: str,
        parameters: dict,
        description: str | None = None,
    ) -> BotActionResult:
        token = self._token()
        response = self.client.create_strategy(
            token,
            name=name,
            strategy_type=strategy_type,
            parameters=parameters,
            description=description,
        )
        if not response.success:
            msg = (
                response.error
                or (response.data.get("detail") if isinstance(response.data, dict) else None)
                or f"Erreur backend ({response.status_code})."
            )
            return BotActionResult(success=False, message=msg)
        return BotActionResult(success=True, message=f"Bot '{name}' créé.")

    def delete_bot(self, bot_id: str) -> BotActionResult:
        token = self._token()
        response = self.client.delete_strategy(token, bot_id)
        if not response.success and response.status_code != 204:
            msg = (
                response.error
                or (response.data.get("detail") if isinstance(response.data, dict) else None)
                or f"Erreur backend ({response.status_code})."
            )
            return BotActionResult(success=False, message=msg)
        return BotActionResult(success=True, message="Bot supprimé.")

    def apply_action(self, bot_id: str, action: str) -> BotActionResult:
        token = self._token()

        if action == ACTION_STOP:
            deployment_id = self._active_deployments.get(bot_id)
            if not deployment_id:
                return BotActionResult(success=False, message="Aucun deployment actif a arreter.")
            response = self.client.stop_deployment(token, deployment_id)
            if not response.success:
                msg = (
                    response.error
                    or (response.data.get("detail") if isinstance(response.data, dict) else None)
                    or f"Erreur backend ({response.status_code})."
                )
                return BotActionResult(success=False, message=msg)
            self._active_deployments.pop(bot_id, None)
            return BotActionResult(success=True, message="Deployment arrete.")

        if action == ACTION_START:
            return BotActionResult(
                success=False,
                message="Utilisez start_bot() en passant les parametres de deployment.",
            )

        # ACTION_PAUSE - pas de endpoint backend dedie
        return BotActionResult(
            success=False,
            message="La mise en pause n'est pas supportee par l'API backend.",
        )

    def start_bot(
        self,
        bot_id: str,
        exchange: str,
        symbol: str,
        timeframe: str,
        amount: float,
        is_paper: bool = True,
    ) -> BotActionResult:
        """Cree un nouveau deployment pour le bot donne."""
        token = self._token()
        response = self.client.deploy_strategy(
            token,
            bot_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            amount=amount,
            is_paper=is_paper,
        )
        if not response.success:
            msg = (
                response.error
                or (response.data.get("detail") if isinstance(response.data, dict) else None)
                or f"Erreur backend ({response.status_code})."
            )
            return BotActionResult(success=False, message=msg)

        mode = "Paper" if is_paper else "Live"
        return BotActionResult(
            success=True,
            message=f"Bot deploye en mode {mode} — {symbol} {timeframe}, capital {amount} USDC.",
        )
