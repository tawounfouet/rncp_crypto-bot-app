"""Admin service backed by backend user management APIs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from mocks.db import MockStore
from schemas.admin import AdminUserDetail, AdminUserRow
from schemas.common import UserRole, UserStatus
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from services.runtime_mode import allow_mock_fallback, backend_required_message
from state.session import get_access_token, get_refresh_token, set_auth_tokens


class AdminService:
    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()
        self._users_by_email: dict[str, AdminUserDetail] = {}

    def _ensure_admin(self) -> None:
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        user = self.store.users[self.store.current_user_email]
        if user.role != UserRole.ADMIN:
            raise ServiceError("Acces admin requis.")

    def list_users(self) -> list[AdminUserRow]:
        access_token = get_access_token()
        if access_token:
            rows = self._list_users_backend()
            self._users_by_email = {row.email.lower(): self._detail_from_row(row) for row in rows}
            return rows
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("l'administration"))
        return self._list_users_mock()

    def _list_users_mock(self) -> list[AdminUserRow]:
        simulate_latency(self.store, min_ms=120, max_ms=260)
        raise_if_forced_error(self.store, "admin.list_users", "Erreur mock admin users.")
        self._ensure_admin()
        rows = [
            AdminUserRow(
                email=user.email,
                role=user.role,
                status=user.status,
                last_login=user.last_login,
                first_name=user.first_name,
                last_name=user.last_name,
                binance_configured=user.binance_configured,
            )
            for user in self.store.users.values()
        ]
        return sorted(rows, key=lambda row: row.email)

    def get_user_detail(self, email: str) -> AdminUserDetail:
        access_token = get_access_token()
        if access_token:
            cached = self._users_by_email.get(email.lower())
            if cached:
                return cached
            rows = self._list_users_backend()
            self._users_by_email = {row.email.lower(): self._detail_from_row(row) for row in rows}
            cached = self._users_by_email.get(email.lower())
            if cached:
                return cached
            raise ServiceError("Utilisateur introuvable.")
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("le detail utilisateur"))
        return self._get_user_detail_mock(email)

    def _get_user_detail_mock(self, email: str) -> AdminUserDetail:
        simulate_latency(self.store, min_ms=80, max_ms=220)
        self._ensure_admin()
        user = self.store.users.get(email.lower())
        if not user:
            raise ServiceError("Utilisateur introuvable.")
        return AdminUserDetail(
            email=user.email,
            role=user.role,
            status=user.status,
            last_login=user.last_login,
            first_name=user.first_name,
            last_name=user.last_name,
            created_at=user.created_at,
            binance_configured=user.binance_configured,
            failed_login_count=user.failed_login_count,
        )

    def set_enabled(self, email: str, enabled: bool) -> tuple[bool, str]:
        access_token = get_access_token()
        if access_token:
            detail = self.get_user_detail(email)
            request_fn = self.client.activate_user if enabled else self.client.deactivate_user
            response = self._request_with_auth_refresh(
                lambda token: request_fn(token, user_id=detail.id)
            )
            if response.success:
                return True, "Statut utilisateur mis a jour."
            return False, self._extract_error_message(response)
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("la mise a jour utilisateur"))
        return self._set_enabled_mock(email, enabled)

    def _set_enabled_mock(self, email: str, enabled: bool) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=100, max_ms=240)
        raise_if_forced_error(self.store, "admin.toggle_status", "Erreur mock toggle statut.")
        self._ensure_admin()
        user = self.store.users.get(email.lower())
        if not user:
            return False, "Utilisateur introuvable."
        if user.email == self.store.current_user_email and not enabled:
            return False, "Impossible de desactiver votre propre compte admin."
        user.status = UserStatus.ENABLED if enabled else UserStatus.DISABLED
        return True, "Statut utilisateur mis a jour."

    def set_role(self, email: str, role: UserRole) -> tuple[bool, str]:
        access_token = get_access_token()
        if access_token:
            detail = self.get_user_detail(email)
            request_fn = (
                self.client.make_user_admin
                if role == UserRole.ADMIN
                else self.client.remove_user_admin
            )
            response = self._request_with_auth_refresh(
                lambda token: request_fn(token, user_id=detail.id)
            )
            if response.success:
                return True, "Role utilisateur mis a jour."
            return False, self._extract_error_message(response)
        if not allow_mock_fallback():
            raise ServiceError(backend_required_message("la mise a jour du role"))
        return self._set_role_mock(email, role)

    def _set_role_mock(self, email: str, role: UserRole) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=100, max_ms=240)
        raise_if_forced_error(self.store, "admin.set_role", "Erreur mock changement role.")
        self._ensure_admin()
        user = self.store.users.get(email.lower())
        if not user:
            return False, "Utilisateur introuvable."
        if user.email == self.store.current_user_email and role != UserRole.ADMIN:
            return False, "Impossible de retirer votre propre role admin."
        user.role = role
        return True, "Role utilisateur mis a jour."

    def _list_users_backend(self) -> list[AdminUserRow]:
        response = self._request_with_auth_refresh(
            lambda token: self.client.list_users(token, limit=1000)
        )
        if response.success and isinstance(response.data, list):
            return sorted(
                [self._row_from_backend(item) for item in response.data if isinstance(item, dict)],
                key=lambda row: row.email,
            )
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

    @staticmethod
    def _row_from_backend(payload: dict[str, Any]) -> AdminUserRow:
        return AdminUserRow(
            id=str(payload.get("id") or ""),
            email=str(payload.get("email") or ""),
            role=UserRole.ADMIN if bool(payload.get("is_admin")) else UserRole.USER,
            status=UserStatus.ENABLED if bool(payload.get("is_active")) else UserStatus.DISABLED,
            last_login=AdminService._parse_datetime(payload.get("last_active_at")),
            first_name=str(payload.get("first_name") or payload.get("username") or ""),
            last_name=payload.get("last_name"),
            binance_configured=bool(payload.get("binance_configured")),
        )

    @staticmethod
    def _detail_from_row(row: AdminUserRow) -> AdminUserDetail:
        return AdminUserDetail(
            **row.model_dump(),
            created_at=datetime.now(UTC),
            failed_login_count=0,
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
            message = payload.get("message")
            if isinstance(message, str) and message:
                return message
        if response.status_code == 0:
            return "API admin indisponible."
        return f"Erreur backend ({response.status_code})."

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        parsed: datetime | None = None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
