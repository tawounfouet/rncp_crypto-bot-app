"""Service de gestion de compte utilisateur - connecte au backend reel."""

from __future__ import annotations

from mocks.db import MockStore
from schemas.account import (
    AccountProfile,
    ApiCredentialEntry,
    ApiCredentialInput,
    BinanceCredentialInput,
    BinanceCredentialStatus,
)
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token, set_binance_configured, sync_current_user_from_backend
from utils.validators import validate_email, validate_required


def _extract_error(response) -> str:
    if response.error:
        return response.error
    data = response.data
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"Erreur backend ({response.status_code})."


class AccountService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()

    def _token(self) -> str:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")
        return token

    def get_profile(self) -> AccountProfile:
        token = self._token()
        response = self.client.get_current_user(token)
        if not response.success:
            raise ServiceError(f"Impossible de charger le profil: {_extract_error(response)}")
        data = response.data or {}
        return AccountProfile(
            first_name=data.get("first_name") or "",
            last_name=data.get("last_name") or None,
            email=data.get("email") or "",
        )

    def update_profile(self, profile: AccountProfile) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        ok, message = validate_required(profile.first_name, "Le prenom")
        if not ok:
            return False, message
        ok, message = validate_email(profile.email)
        if not ok:
            return False, message

        response = self.client.update_user(
            token,
            first_name=profile.first_name.strip(),
            last_name=(profile.last_name or "").strip() or None,
            email=profile.email.strip().lower(),
        )
        if not response.success:
            return False, _extract_error(response)

        if isinstance(response.data, dict):
            sync_current_user_from_backend(response.data, store=self.store, access_token=token)

        return True, "Profil mis a jour."

    def get_binance_status(self) -> BinanceCredentialStatus:
        try:
            token = self._token()
        except ServiceError:
            return BinanceCredentialStatus(configured=False)

        response = self.client.get_user_settings(token)
        if not response.success:
            return BinanceCredentialStatus(configured=False)

        data = response.data or {}
        # L'endpoint retourne has_binance_credentials=True/False ou api_keys.binance present
        if "has_binance_credentials" in data:
            configured = bool(data["has_binance_credentials"])
        else:
            api_keys = data.get("api_keys") or {}
            configured = bool(api_keys.get("binance"))

        set_binance_configured(configured, store=self.store)

        return BinanceCredentialStatus(
            configured=configured,
            api_key_masked="sk_****" if configured else "",
            api_secret_masked="sk_****" if configured else "",
        )

    def save_binance_credentials(self, payload: BinanceCredentialInput) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        for value, label in [
            (payload.api_key, "L'API key"),
            (payload.api_secret, "L'API secret"),
        ]:
            ok, msg = validate_required(value, label)
            if not ok:
                return False, msg

        response = self.client.update_user_settings(
            token,
            binance_api_key=payload.api_key.strip(),
            binance_api_secret=payload.api_secret.strip(),
        )
        if not response.success:
            return False, _extract_error(response)

        set_binance_configured(True, store=self.store)
        return True, "Cles Binance enregistrees et chiffrees en base."

    # -------------------------------------------------------------------------
    # Multi-credential management
    # -------------------------------------------------------------------------

    def list_credentials(self) -> list[ApiCredentialEntry]:
        try:
            token = self._token()
        except ServiceError:
            return []
        response = self.client.list_api_credentials(token)
        if not response.success or not isinstance(response.data, list):
            return []
        return [
            ApiCredentialEntry(
                id=c.get("id", ""),
                exchange=c.get("exchange", "binance"),
                label=c.get("label", ""),
                api_key_masked=c.get("api_key_masked", "****"),
                created_at=c.get("created_at"),
                is_primary=c.get("is_primary", False),
            )
            for c in response.data
        ]

    def add_credential(self, payload: ApiCredentialInput) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        if not payload.label.strip():
            return False, "Le label est requis."
        if not payload.api_key.strip() or not payload.api_secret.strip():
            return False, "La clef API et le secret sont requis."

        response = self.client.add_api_credential(
            token,
            label=payload.label.strip(),
            exchange=payload.exchange.strip().lower(),
            api_key=payload.api_key.strip(),
            api_secret=payload.api_secret.strip(),
        )
        if not response.success:
            return False, _extract_error(response)

        set_binance_configured(True, store=self.store)
        return True, f"Clef '{payload.label}' ajoutee et chiffree en base."

    def set_primary_credential(self, key_id: str) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)
        response = self.client.set_primary_api_credential(token, key_id)
        if not response.success:
            return False, _extract_error(response)
        return True, "Clef définie comme principale."

    def delete_credential(self, key_id: str) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        response = self.client.delete_api_credential(token, key_id)
        if not response.success and response.status_code != 204:
            return False, _extract_error(response)
        return True, "Clef supprimee."
