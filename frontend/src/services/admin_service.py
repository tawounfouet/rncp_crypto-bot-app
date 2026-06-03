"""Service admin mocke."""

from __future__ import annotations

from mocks.db import MockStore
from schemas.admin import AdminUserDetail, AdminUserRow
from schemas.common import UserRole, UserStatus
from services.base import ServiceError, raise_if_forced_error, simulate_latency


class AdminService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def _ensure_admin(self) -> None:
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        user = self.store.users[self.store.current_user_email]
        if user.role != UserRole.ADMIN:
            raise ServiceError("Acces admin requis.")

    def list_users(self) -> list[AdminUserRow]:
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
