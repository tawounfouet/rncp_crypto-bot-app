"""Service admin - connecte au backend reel."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.admin import AdminUserDetail, AdminUserRow
from schemas.common import UserRole, UserStatus
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return None


def _extract_error(response) -> str:
    if response.error:
        return response.error
    data = response.data
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"Erreur backend ({response.status_code})."


class AdminService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()
        self._user_list: list[dict] = []

    def _token(self) -> str:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")
        return token

    def _ensure_admin(self) -> None:
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        user = self.store.users.get(self.store.current_user_email)
        if user and user.role != UserRole.ADMIN:
            raise ServiceError("Acces admin requis.")

    def _to_row(self, u: dict) -> AdminUserRow:
        return AdminUserRow(
            email=u.get("email", ""),
            role=UserRole.ADMIN if u.get("is_admin") else UserRole.USER,
            status=UserStatus.ENABLED if u.get("is_active", True) else UserStatus.DISABLED,
            last_login=_parse_dt(u.get("last_active_at")),
            first_name=u.get("first_name") or "",
            last_name=u.get("last_name") or None,
            exchange_configured=False,
        )

    def list_users(self) -> list[AdminUserRow]:
        self._ensure_admin()
        token = self._token()
        response = self.client.list_users(token)
        if not response.success:
            raise ServiceError(f"Impossible de lister les utilisateurs: {_extract_error(response)}")

        raw = response.data
        self._user_list = raw if isinstance(raw, list) else []
        return sorted([self._to_row(u) for u in self._user_list], key=lambda r: r.email)

    def _find_user(self, email: str) -> dict | None:
        email_lower = email.lower()
        return next(
            (u for u in self._user_list if (u.get("email") or "").lower() == email_lower),
            None,
        )

    def get_user_detail(self, email: str) -> AdminUserDetail:
        self._ensure_admin()
        user = self._find_user(email)
        if not user:
            raise ServiceError("Utilisateur introuvable.")
        return AdminUserDetail(
            email=user.get("email", ""),
            role=UserRole.ADMIN if user.get("is_admin") else UserRole.USER,
            status=UserStatus.ENABLED if user.get("is_active", True) else UserStatus.DISABLED,
            last_login=_parse_dt(user.get("last_active_at")),
            first_name=user.get("first_name") or "",
            last_name=user.get("last_name") or None,
            created_at=_parse_dt(user.get("created_at")) or datetime.now(UTC),
            exchange_configured=False,
            failed_login_count=0,
        )

    def set_enabled(self, email: str, enabled: bool) -> tuple[bool, str]:
        self._ensure_admin()
        user = self._find_user(email)
        if not user:
            return False, "Utilisateur introuvable."

        # Prevent self-deactivation
        if (
            not enabled
            and self.store.current_user_email
            and (user.get("email") or "").lower() == self.store.current_user_email.lower()
        ):
            return False, "Impossible de desactiver votre propre compte admin."

        token = self._token()
        if enabled:
            response = self.client.activate_user(token, user["id"])
        else:
            response = self.client.deactivate_user(token, user["id"])

        if not response.success:
            return False, _extract_error(response)
        return True, "Statut utilisateur mis a jour."

    def set_role(self, email: str, role: UserRole) -> tuple[bool, str]:
        # Pas d'endpoint backend dedie au changement de role pour l'instant
        return False, "Changement de role non disponible via l'API backend."
