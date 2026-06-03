"""Service de gestion de compte utilisateur."""

from __future__ import annotations

from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.account import AccountProfile, BinanceCredentialInput, BinanceCredentialStatus
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from utils.formatters import mask_secret
from utils.validators import validate_email, validate_required


class AccountService:
    def __init__(self, store: MockStore) -> None:
        self.store = store

    def _current_user(self):
        if not self.store.current_user_email:
            raise ServiceError("Utilisateur non connecte.")
        user = self.store.users.get(self.store.current_user_email.lower())
        if not user:
            raise ServiceError("Utilisateur introuvable.")
        return user

    def get_profile(self) -> AccountProfile:
        simulate_latency(self.store, min_ms=80, max_ms=220)
        user = self._current_user()
        return AccountProfile(
            first_name=user.first_name, last_name=user.last_name, email=user.email
        )

    def update_profile(self, profile: AccountProfile) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=120, max_ms=260)
        raise_if_forced_error(self.store, "account.profile.update", "Maj profil impossible (mock).")
        user = self._current_user()

        ok, message = validate_required(profile.first_name, "Le prenom")
        if not ok:
            return False, message
        ok, message = validate_email(profile.email)
        if not ok:
            return False, message

        normalized_email = profile.email.lower().strip()
        if normalized_email != user.email and normalized_email in self.store.users:
            return False, "Cet email est deja utilise."

        if normalized_email != user.email:
            previous_email = user.email
            del self.store.users[previous_email]
            user.email = normalized_email
            self.store.users[user.email] = user
            self.store.current_user_email = user.email
            if previous_email in self.store.binance_credentials:
                self.store.binance_credentials[user.email] = self.store.binance_credentials.pop(
                    previous_email
                )
            if previous_email in self.store.credential_updated_at:
                self.store.credential_updated_at[user.email] = self.store.credential_updated_at.pop(
                    previous_email
                )

        user.first_name = profile.first_name.strip()
        user.last_name = (profile.last_name or "").strip() or None
        return True, "Profil mis a jour."

    def get_binance_status(self) -> BinanceCredentialStatus:
        simulate_latency(self.store, min_ms=80, max_ms=220)
        user = self._current_user()
        raw = self.store.binance_credentials.get(user.email.lower())
        updated_at = self.store.credential_updated_at.get(user.email.lower())
        if not raw:
            return BinanceCredentialStatus(configured=False, updated_at=updated_at)
        api_key, api_secret = raw
        return BinanceCredentialStatus(
            configured=True,
            updated_at=updated_at,
            api_key_masked=mask_secret(api_key),
            api_secret_masked=mask_secret(api_secret),
        )

    def save_binance_credentials(self, payload: BinanceCredentialInput) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=120, max_ms=280)
        raise_if_forced_error(
            self.store,
            "account.binance.save",
            "Enregistrement des cles impossible (mock).",
        )
        user = self._current_user()

        checks = [
            validate_required(payload.api_key, "L'API key"),
            validate_required(payload.api_secret, "L'API secret"),
            validate_required(payload.password_confirmation, "La confirmation mot de passe"),
        ]
        for ok, message in checks:
            if not ok:
                return False, message
        if payload.password_confirmation != user.password:
            return False, "Mot de passe de confirmation invalide."

        self.store.binance_credentials[user.email.lower()] = (payload.api_key, payload.api_secret)
        self.store.credential_updated_at[user.email.lower()] = datetime.now(UTC)
        user.binance_configured = True
        return True, "Cles Binance enregistrees."
