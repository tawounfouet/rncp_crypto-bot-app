"""Service de gestion de compte utilisateur - connecte au backend reel."""

from __future__ import annotations

from mocks.db import MockStore
from schemas.account import (
    AccountProfile,
    ApiCredentialEntry,
    ApiCredentialInput,
    ExchangeCredentialInput,
    ExchangeCredentialStatus,
)
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import (
    get_access_token,
    get_selected_exchange,
    set_exchange_configured,
    sync_current_user_from_backend,
)
from utils.api_errors import extract_error as _extract_error
from utils.validators import validate_email, validate_required


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

    def get_exchange_capabilities(self) -> dict[str, bool]:
        """Retourne {exchange: supports_sandbox} depuis le catalogue public des exchanges."""
        response = self.client.get_public_exchanges()
        if not response.success:
            return {}
        data = response.data or {}
        items = data.get("data") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return {}
        return {
            item["id"]: bool(item.get("supports_sandbox"))
            for item in items
            if isinstance(item, dict)
        }

    def get_exchange_status(self, exchange: str) -> ExchangeCredentialStatus:
        supports_sandbox = self.get_exchange_capabilities().get(exchange, False)

        try:
            token = self._token()
        except ServiceError:
            return ExchangeCredentialStatus(
                exchange=exchange, configured=False, supports_sandbox=supports_sandbox
            )

        response = self.client.get_user_settings(token)
        if not response.success:
            return ExchangeCredentialStatus(
                exchange=exchange, configured=False, supports_sandbox=supports_sandbox
            )

        data = response.data or {}
        detail_map = data.get("exchange_credentials")
        if detail_map is not None:
            detail = detail_map.get(exchange, {})
            live_configured = bool(detail.get("live"))
            sandbox_configured = bool(detail.get("sandbox"))
            configured = live_configured or sandbox_configured
            active_mode = detail.get("active_mode", "live")
        else:
            # Ancien contrat de reponse (sans detail par mode) : deduit du seul flag "configure".
            configured = exchange in (data.get("configured_exchanges") or [])
            live_configured = configured
            sandbox_configured = False
            active_mode = "live"

        set_exchange_configured(configured, store=self.store)

        return ExchangeCredentialStatus(
            exchange=exchange,
            configured=configured,
            live_configured=live_configured,
            sandbox_configured=sandbox_configured,
            active_mode=active_mode,
            supports_sandbox=supports_sandbox,
            api_key_masked="sk_****" if configured else "",
            api_secret_masked="sk_****" if configured else "",
        )

    def get_active_modes(self, exchanges: list[str]) -> dict[str, str]:
        """Mode actif ("live"/"sandbox") par exchange, sans effet de bord sur l'etat de session."""
        try:
            token = self._token()
        except ServiceError:
            return {}

        response = self.client.get_user_settings(token)
        if not response.success:
            return {}

        data = response.data or {}
        detail_map = data.get("exchange_credentials") or {}
        return {
            exchange: detail_map.get(exchange, {}).get("active_mode", "live")
            for exchange in exchanges
        }

    def save_exchange_credentials(self, payload: ExchangeCredentialInput) -> tuple[bool, str]:
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
            exchange=payload.exchange,
            api_key=payload.api_key.strip(),
            api_secret=payload.api_secret.strip(),
            mode=payload.mode,
        )
        if not response.success:
            return False, _extract_error(response)

        set_exchange_configured(True, store=self.store)
        return True, "Cles enregistrees et chiffrees en base."

    def set_active_mode(self, exchange: str, mode: str) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        response = self.client.update_user_settings(token, exchange=exchange, mode=mode)
        if not response.success:
            return False, _extract_error(response)

        return True, "Mode actif mis a jour."

    def list_configured_exchanges(self) -> list[str]:
        try:
            token = self._token()
        except ServiceError:
            return []

        response = self.client.get_user_settings(token)
        if not response.success:
            return []

        data = response.data or {}
        if "configured_exchanges" in data:
            return sorted(data["configured_exchanges"] or [])
        api_keys = data.get("api_keys") or {}
        return sorted(api_keys.keys())

    def delete_exchange_credentials(self, exchange: str) -> tuple[bool, str]:
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc)

        response = self.client.update_user_settings(
            token, exchange=exchange, api_key="", api_secret=""
        )
        if not response.success:
            return False, _extract_error(response)

        if exchange == get_selected_exchange():
            set_exchange_configured(False, store=self.store)
        return True, "Cles supprimees."

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

        set_exchange_configured(True, store=self.store)
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
