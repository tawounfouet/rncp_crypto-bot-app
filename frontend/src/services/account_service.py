"""Service de gestion de compte utilisateur."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from mocks.db import MockStore
from schemas.account import AccountProfile, BinanceCredentialInput, BinanceCredentialStatus
from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError, raise_if_forced_error, simulate_latency
from state.session import get_access_token, get_refresh_token, set_auth_tokens
from utils.formatters import mask_secret
from utils.validators import validate_email, validate_required


class AccountService:
    def __init__(self, store: MockStore, client: AuthApiClient | None = None) -> None:
        self.store = store
        self.client = client or AuthApiClient()

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
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.get_binance_credentials_status(token)
            )
            if not response.success:
                raise ServiceError(self._extract_error_message(response))
            status = self._status_from_backend(response.data)
            self._set_local_binance_configured(status.configured)
            return status

        return self._get_binance_status_mock()

    def _get_binance_status_mock(self) -> BinanceCredentialStatus:
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
        checks = [
            validate_required(payload.api_key, "L'API key"),
            validate_required(payload.api_secret, "L'API secret"),
            validate_required(payload.password_confirmation, "La confirmation mot de passe"),
        ]
        for ok, message in checks:
            if not ok:
                return False, message

        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.save_binance_credentials(
                    access_token=token,
                    api_key=payload.api_key,
                    api_secret=payload.api_secret,
                    password_confirmation=payload.password_confirmation,
                )
            )
            if not response.success:
                return False, self._extract_error_message(response)
            status = self._status_from_backend(response.data)
            self._set_local_binance_configured(status.configured)
            return True, "Cles Binance chiffrees et enregistrees en base."

        return self._save_binance_credentials_mock(payload)

    def _save_binance_credentials_mock(self, payload: BinanceCredentialInput) -> tuple[bool, str]:
        simulate_latency(self.store, min_ms=120, max_ms=280)
        raise_if_forced_error(
            self.store,
            "account.binance.save",
            "Enregistrement des cles impossible (mock).",
        )
        user = self._current_user()

        if payload.password_confirmation != user.password:
            return False, "Mot de passe de confirmation invalide."

        self.store.binance_credentials[user.email.lower()] = (payload.api_key, payload.api_secret)
        self.store.credential_updated_at[user.email.lower()] = datetime.now(UTC)
        user.binance_configured = True
        return True, "Cles Binance enregistrees."

    def delete_binance_credentials(self) -> tuple[bool, str]:
        access_token = get_access_token()
        if access_token:
            response = self._request_with_auth_refresh(
                lambda token: self.client.delete_binance_credentials(token)
            )
            if not response.success:
                return False, self._extract_error_message(response)
            self._set_local_binance_configured(False)
            return True, "Cles Binance supprimees de la base."

        user = self._current_user()
        self.store.binance_credentials.pop(user.email.lower(), None)
        self.store.credential_updated_at[user.email.lower()] = datetime.now(UTC)
        user.binance_configured = False
        return True, "Cles Binance supprimees."

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

    def _status_from_backend(self, payload: object) -> BinanceCredentialStatus:
        if not isinstance(payload, dict):
            raise ServiceError("Reponse backend Binance invalide.")
        return BinanceCredentialStatus(
            configured=bool(payload.get("configured")),
            updated_at=self._parse_datetime(payload.get("updated_at")),
            api_key_masked=str(payload.get("api_key_masked") or ""),
            api_secret_masked="",
        )

    def _set_local_binance_configured(self, configured: bool) -> None:
        if not self.store.current_user_email:
            return
        user = self.store.users.get(self.store.current_user_email.lower())
        if user:
            user.binance_configured = configured

    def _extract_error_message(self, response: ApiResponse) -> str:
        if response.error:
            return response.error
        payload = response.data
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, str) and detail:
                if detail == "Invalid password confirmation":
                    return "Mot de passe de confirmation invalide."
                return detail
            details = payload.get("details")
            if isinstance(details, list) and details:
                first_error = details[0]
                if isinstance(first_error, dict):
                    message = first_error.get("msg")
                    if isinstance(message, str) and message:
                        return message
        if response.status_code == 0:
            return "API compte indisponible."
        return f"Erreur backend ({response.status_code})."

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str) and value.strip():
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None
