"""Service de controle des bots Spot."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from mocks.db import MockStore
from mocks.scenarios import MockScenario
from schemas.bot import BotActionResult, BotInfo
from schemas.common import BotRuntimeStatus
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from services.runtime_mode import allow_mock_fallback, backend_required_message
from state.session import get_access_token, get_refresh_token, set_auth_tokens
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP

MISSING_VALUE = "-"


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _clean_text(value: object, *, default: str = MISSING_VALUE) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _format_registry_source(value: object) -> str:
    raw = _clean_text(value).lower()
    if raw == "mlflow":
        return "MLflow"
    if raw == MISSING_VALUE:
        return MISSING_VALUE
    return _clean_text(value)


def _format_model_source(value: object) -> str:
    raw = _clean_text(value).lower()
    if raw == "ml_api":
        return "ML API"
    return "Moteur déterministe"


def _format_model_version(value: object) -> str:
    text = _clean_text(value)
    if text == MISSING_VALUE:
        return MISSING_VALUE
    return text if text.lower().startswith("v") else f"v{text}"


def _format_confidence(value: object) -> str:
    if value is None or value == "":
        return MISSING_VALUE
    try:
        number = float(value)
    except (TypeError, ValueError):
        return _clean_text(value)
    if 0 <= number <= 1:
        return f"{number:.1%}"
    return f"{number:.3f}"


def _format_feature_value(value: object) -> object:
    if isinstance(value, float):
        return round(value, 8)
    return value if value is not None else MISSING_VALUE


def normalise_decision_trace(decision: dict[str, Any]) -> dict[str, Any]:
    """Flatten backend trading_decisions.model_output into readable UI fields."""
    model_output = _mapping(decision.get("model_output"))
    model_result = _mapping(model_output.get("model_result"))
    features = _mapping(model_output.get("features"))
    model_source_raw = _clean_text(
        model_output.get("model_source"), default="deterministic"
    ).lower()
    is_ml_api = model_source_raw == "ml_api"
    model_name = (
        model_output.get("model_name")
        or model_output.get("model_type")
        or model_result.get("model_type")
        or decision.get("model_type")
    )
    deterministic_signal = (
        model_output.get("deterministic_signal")
        or model_output.get("strategy_action")
        or decision.get("strategy_signal")
    )
    raw_ai_signal = model_output.get("raw_ai_signal") if is_ml_api else None
    signal_for_badge = raw_ai_signal or deterministic_signal or decision.get("strategy_signal")

    return {
        "id": _clean_text(decision.get("id")),
        "timestamp": decision.get("timestamp"),
        "model_source": _format_model_source(model_output.get("model_source")),
        "model_source_raw": model_source_raw,
        "registry_source": _format_registry_source(model_output.get("registry_source")),
        "model_name": _clean_text(model_name),
        "model_version": _format_model_version(model_output.get("model_version")),
        "confidence": _format_confidence(model_output.get("confidence")),
        "confidence_raw": model_output.get("confidence"),
        "raw_ai_signal": _clean_text(raw_ai_signal),
        "deterministic_signal": _clean_text(deterministic_signal),
        "signal": _clean_text(signal_for_badge),
        "final_action": _clean_text(decision.get("final_action")),
        "risk_decision": _clean_text(decision.get("risk_decision")),
        "reason": _clean_text(decision.get("reason")),
        "features": {str(key): _format_feature_value(value) for key, value in features.items()},
        "order_expected": _clean_text(decision.get("final_action")).upper() in {"BUY", "SELL"},
    }


def is_error_decision_trace(trace: dict[str, Any]) -> bool:
    for key in ("signal", "raw_ai_signal", "final_action", "risk_decision"):
        if _clean_text(trace.get(key)).upper() == "ERROR":
            return True
    return False


def select_badge_decision_trace(traces: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Select the trace used by the main IA badge.

    Backend decisions are already returned newest first. The badge must ignore
    ERROR decisions and prefer the newest ML API decision over deterministic
    traces so a transient worker error does not hide a valid IA state.
    """
    valid_traces = [trace for trace in traces if not is_error_decision_trace(trace)]
    ml_api_traces = [
        trace
        for trace in valid_traces
        if _clean_text(trace.get("model_source_raw")).lower() == "ml_api"
    ]
    if ml_api_traces:
        return ml_api_traces[0]
    if valid_traces:
        return valid_traces[0]
    return None


def ai_labels_from_snapshot(snapshot: dict[str, object]) -> dict[str, str]:
    params = _mapping(snapshot.get("execution_params"))
    model_type = _clean_text(snapshot.get("model_type")).lower()
    model_name = params.get("mlflow_model_name")
    if model_type == "mlflow_bot_rsi_reversal_v1" or model_name:
        return {
            "model_source_label": "ML API",
            "registry_source_label": "MLflow",
            "model_name": _clean_text(model_name),
            "model_version": _format_model_version(params.get("mlflow_model_version")),
        }
    return {
        "model_source_label": "Moteur déterministe",
        "registry_source_label": MISSING_VALUE,
        "model_name": _clean_text(snapshot.get("model_type")),
        "model_version": MISSING_VALUE,
    }


class BotControlService:
    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()

    def has_backend_session(self) -> bool:
        return bool(get_access_token())

    def list_bots(self) -> list[BotInfo]:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.list_user_bots(token)
            )
            if response.success and isinstance(response.data, list):
                return sorted(
                    [self._bot_from_backend(item) for item in response.data],
                    key=lambda bot: bot.name,
                )
            raise ServiceError(self._extract_error_message(response))
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("les bots Spot"))
        return self._list_bots_mock()

    def _list_bots_mock(self) -> list[BotInfo]:
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
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self._apply_backend_action(token, bot_id, action)
            )
            if response.success and isinstance(response.data, dict):
                return self._action_result_from_backend(response.data)
            return BotActionResult(success=False, message=self._extract_error_message(response))
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("les actions de bot"))
        return self._apply_action_mock(bot_id, action)

    def list_decisions(self, bot_id: str) -> list[dict[str, Any]]:
        return self._backend_list(
            lambda token: self.client.list_user_bot_decisions(token, instance_id=bot_id)
        )

    def list_orders(self, bot_id: str) -> list[dict[str, Any]]:
        return self._backend_list(
            lambda token: self.client.list_user_bot_orders(token, instance_id=bot_id)
        )

    def list_trades(self, bot_id: str) -> list[dict[str, Any]]:
        return self._backend_list(
            lambda token: self.client.list_user_bot_trades(token, instance_id=bot_id)
        )

    def get_position(self, bot_id: str) -> dict[str, Any] | None:
        access_token = get_access_token()
        if not access_token:
            if not allow_mock_fallback():
                raise ServiceError(backend_required_message("la position du bot"))
            return None
        response = self._request_with_auth_refresh(
            lambda token: self.client.get_user_bot_position(token, instance_id=bot_id)
        )
        if response.status_code == 0:
            raise ServiceError(self._extract_error_message(response))
        if response.data is None:
            return None
        if response.success and isinstance(response.data, dict):
            return response.data
        raise ServiceError(self._extract_error_message(response))

    def get_performance(self, bot_id: str) -> dict[str, Any] | None:
        access_token = get_access_token()
        if not access_token:
            if not allow_mock_fallback():
                raise ServiceError(backend_required_message("les performances du bot"))
            return None
        response = self._request_with_auth_refresh(
            lambda token: self.client.get_user_bot_performance(token, instance_id=bot_id)
        )
        if response.status_code == 0:
            raise ServiceError(self._extract_error_message(response))
        if response.data is None:
            return None
        if response.success and isinstance(response.data, dict):
            return response.data
        raise ServiceError(self._extract_error_message(response))

    def _apply_action_mock(self, bot_id: str, action: str) -> BotActionResult:
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

    def _apply_backend_action(self, access_token: str, bot_id: str, action: str) -> ApiResponse:
        if action == ACTION_START:
            return self.client.start_user_bot(access_token, instance_id=bot_id)
        if action == ACTION_PAUSE:
            return self.client.pause_user_bot(access_token, instance_id=bot_id)
        if action == ACTION_STOP:
            return self.client.stop_user_bot(access_token, instance_id=bot_id)
        return ApiResponse(status_code=400, data={"detail": "Action non supportee."})

    def _backend_list(self, request_fn: Callable[[str], ApiResponse]) -> list[dict[str, Any]]:
        access_token = get_access_token()
        if not access_token:
            if not allow_mock_fallback():
                raise ServiceError(backend_required_message("le journal d'execution"))
            return []
        response = self._request_with_auth_refresh(request_fn)
        if response.success and isinstance(response.data, list):
            return [item for item in response.data if isinstance(item, dict)]
        raise ServiceError(self._extract_error_message(response))

    def _request_with_auth_refresh(
        self,
        request_fn: Callable[[str], ApiResponse],
    ) -> ApiResponse:
        access_token = get_access_token()
        if not access_token:
            return ApiResponse(status_code=0, error="Utilisateur non connecte.")

        response = request_fn(access_token)
        if response.status_code != 401:
            return response

        refresh_token = get_refresh_token()
        if not refresh_token:
            return response

        refresh_response = self.client.refresh_token(refresh_token)
        if not refresh_response.success or not isinstance(refresh_response.data, dict):
            return response

        new_access_token = refresh_response.data.get("access_token")
        if not isinstance(new_access_token, str) or not new_access_token:
            return response

        set_auth_tokens(new_access_token, refresh_token)
        return request_fn(new_access_token)

    def _bot_from_backend(self, payload: dict[str, Any]) -> BotInfo:
        snapshot = dict(payload.get("config_snapshot") or {})
        template = payload.get("template") if isinstance(payload.get("template"), dict) else {}
        status = self._status_from_backend(str(payload.get("status") or "STOPPED"))
        updated_at = self._parse_datetime(payload.get("updated_at"))
        heartbeat_at = self._parse_datetime(payload.get("last_decision_at"), fallback=updated_at)
        mode_label = str(payload.get("mode") or snapshot.get("environment") or "PAPER").upper()
        ai_labels = ai_labels_from_snapshot(snapshot)
        return BotInfo(
            id=str(payload.get("id", "")),
            name=str(snapshot.get("name") or template.get("name") or "Bot Spot"),
            strategy=str(
                snapshot.get("strategy_type") or template.get("strategy_type") or "preconfigure"
            ),
            mode_live=mode_label == "LIVE",
            mode_label=mode_label,
            status=status,
            heartbeat_at=heartbeat_at,
            last_action_result=str(payload.get("status") or status.value),
            last_action_at=updated_at,
            **ai_labels,
        )

    def _action_result_from_backend(self, payload: dict[str, Any]) -> BotActionResult:
        bot_payload = payload.get("bot")
        bot = self._bot_from_backend(bot_payload) if isinstance(bot_payload, dict) else None
        return BotActionResult(
            success=bool(payload.get("success", True)),
            message=str(payload.get("message") or "Action appliquee."),
            bot=bot,
        )

    @staticmethod
    def _status_from_backend(raw_status: str) -> BotRuntimeStatus:
        if raw_status == "ACTIVE":
            return BotRuntimeStatus.RUNNING
        return BotRuntimeStatus(raw_status)

    @staticmethod
    def _extract_error_message(response: ApiResponse) -> str:
        if response.error:
            return response.error
        payload = response.data
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                return detail
            if isinstance(detail, dict):
                message = detail.get("message")
                if isinstance(message, str) and message:
                    return message
            details = payload.get("details")
            if isinstance(details, list) and details:
                first = details[0]
                if isinstance(first, dict) and isinstance(first.get("msg"), str):
                    return str(first["msg"])
        if response.status_code == 0:
            return "API bots indisponible."
        return f"Erreur backend ({response.status_code})."

    @staticmethod
    def _parse_datetime(value: object, *, fallback: datetime | None = None) -> datetime:
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        if parsed is None:
            parsed = fallback or datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
