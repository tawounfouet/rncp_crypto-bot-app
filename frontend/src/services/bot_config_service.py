"""Service de catalogue des bots Spot preconfigures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from mocks.db import MockStore
from schemas.bot import BotTemplate, UserBotSelection
from schemas.common import BotRuntimeStatus
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from services.runtime_mode import allow_mock_fallback, backend_required_message
from state.session import get_access_token, get_refresh_token, set_auth_tokens


class BotConfigService:
    """Expose des bots verrouilles: selection oui, parametrage utilisateur non."""

    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()

    def list_templates(self) -> list[BotTemplate]:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.list_bot_templates(token)
            )
            if response.success and isinstance(response.data, list):
                return sorted(
                    [self._template_from_backend(item) for item in response.data],
                    key=lambda template: template.name,
                )
            raise ServiceError(self._extract_error_message(response))
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("le catalogue des bots"))
        return self._list_templates_mock()

    def _list_templates_mock(self) -> list[BotTemplate]:
        simulate_latency(self.store, min_ms=90, max_ms=240)
        raise_if_forced_error(self.store, "bot_templates.list", "Lecture catalogue impossible.")
        return sorted(self.store.bot_templates.values(), key=lambda template: template.name)

    def get_template(self, template_id: str) -> BotTemplate:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.get_bot_template(template_id, token)
            )
            if response.success and isinstance(response.data, dict):
                return self._template_from_backend(response.data)
            raise ServiceError(self._extract_error_message(response))
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("le bot preconfigure"))
        return self._get_template_mock(template_id)

    def _get_template_mock(self, template_id: str) -> BotTemplate:
        simulate_latency(self.store, min_ms=60, max_ms=180)
        raise_if_forced_error(self.store, "bot_templates.fetch", "Lecture bot impossible.")
        template = self.store.bot_templates.get(template_id)
        if not template:
            raise ServiceError("Bot preconfigure introuvable.")
        return template

    def list_user_selections(self) -> list[UserBotSelection]:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.list_user_bots(token)
            )
            if response.success and isinstance(response.data, list):
                return [self._selection_from_backend(item) for item in response.data]
            raise ServiceError(self._extract_error_message(response))
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("vos bots selectionnes"))
        email = self._current_email()
        return list(self.store.user_bot_selections.get(email, []))

    def is_selected(self, template_id: str) -> bool:
        return any(
            selection.template_id == template_id for selection in self.list_user_selections()
        )

    def _is_selected_mock(self, email: str, template_id: str) -> bool:
        return any(
            selection.template_id == template_id
            for selection in self.store.user_bot_selections.get(email, [])
        )

    def select_template(self, template_id: str) -> tuple[bool, str, UserBotSelection | None]:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.create_user_bot(token, template_id=template_id)
            )
            if response.success and isinstance(response.data, dict):
                return (
                    True,
                    "Bot ajoute a vos instances. Sa configuration est verrouillee.",
                    self._selection_from_backend(response.data),
                )
            if response.status_code == 409:
                return False, "Ce bot est deja selectionne.", None
            return False, self._extract_error_message(response), None
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("la selection de bot"))
        return self._select_template_mock(template_id)

    def _select_template_mock(self, template_id: str) -> tuple[bool, str, UserBotSelection | None]:
        simulate_latency(self.store, min_ms=120, max_ms=280)
        raise_if_forced_error(self.store, "bot_templates.select", "Selection bot impossible.")
        email = self._current_email()
        template = self.store.bot_templates.get(template_id)
        if not template:
            return False, "Bot preconfigure introuvable.", None
        if self._is_selected_mock(email, template_id):
            return False, "Ce bot est deja selectionne.", None

        selection = UserBotSelection(
            id=f"sel_{email.replace('@', '_at_')}_{template_id}",
            template_id=template_id,
            user_email=email,
            status="STOPPED",
            auto_trade_enabled=False,
            config_snapshot=template.model_dump(),
            created_at=datetime.now(UTC),
        )
        self.store.user_bot_selections.setdefault(email, []).append(selection)
        return True, "Bot ajoute a vos instances. Sa configuration est verrouillee.", selection

    def _current_email(self) -> str:
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        return self.store.current_user_email.lower()

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

    def _template_from_backend(self, payload: dict[str, Any]) -> BotTemplate:
        return BotTemplate(
            id=str(payload.get("id", "")),
            name=str(payload.get("name", "")),
            description=str(payload.get("description") or ""),
            model_type=str(payload.get("model_type", "")),
            strategy_type=str(payload.get("strategy_type", "")),
            exchange=str(payload.get("exchange") or "-"),
            symbol=str(payload.get("symbol", "")),
            timeframe=str(payload.get("timeframe", "")),
            signal_source=str(payload.get("signal_source", "")),
            execution_params=dict(payload.get("execution_params") or {}),
            risk_limits=dict(payload.get("risk_limits") or {}),
            order_policy=dict(payload.get("order_policy") or {}),
            version=str(payload.get("version") or "1.0"),
            status=str(payload.get("status") or "published"),
        )

    def _selection_from_backend(self, payload: dict[str, Any]) -> UserBotSelection:
        snapshot = dict(payload.get("config_snapshot") or {})
        raw_status = str(payload.get("status") or "STOPPED")
        status = (
            BotRuntimeStatus.RUNNING if raw_status == "ACTIVE" else BotRuntimeStatus(raw_status)
        )
        return UserBotSelection(
            id=str(payload.get("id", "")),
            template_id=str(payload.get("bot_template_id") or snapshot.get("template_id") or ""),
            user_email=(self.store.current_user_email or str(payload.get("user_id") or "")).lower(),
            status=status,
            auto_trade_enabled=bool(payload.get("auto_trade_enabled")),
            config_snapshot=snapshot,
            created_at=self._parse_datetime(payload.get("created_at")),
        )

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
    def _parse_datetime(value: object) -> datetime:
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        if parsed is None:
            parsed = datetime.now(UTC)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
