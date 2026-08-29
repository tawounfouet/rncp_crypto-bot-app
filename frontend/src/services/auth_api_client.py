"""HTTP client for the backend authentication endpoints."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

DEFAULT_TIMEOUT_SECONDS = 30
API_PREFIX = "/api/v1"


@dataclass
class ApiResponse:
    status_code: int
    data: Any = None
    error: str | None = None
    headers: Mapping[str, str] | None = None

    @property
    def success(self) -> bool:
        return self.error is None and self.status_code < 400


class AuthApiClient:
    """Thin client over the existing FastAPI auth endpoints."""

    def __init__(self, base_url: str | None = None, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> None:
        resolved_base_url = (base_url or os.getenv("API_URL", "http://localhost:8009")).rstrip("/")
        self.base_url = resolved_base_url
        self.timeout = timeout

    def register(
        self,
        *,
        email: str,
        username: str,
        password: str,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {
            "email": email,
            "username": username,
            "password": password,
        }
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        return self._request("POST", f"{API_PREFIX}/auth/register", json_body=payload)

    def login_json(self, *, username: str, password: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/login/json",
            json_body={"username": username, "password": password},
        )

    def login_form(self, *, username: str, password: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/login",
            form_body={"username": username, "password": password},
        )

    def refresh_token(self, refresh_token: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/refresh",
            query_params={"refresh_token": refresh_token},
        )

    def logout(self, refresh_token: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/auth/logout",
            query_params={"refresh_token": refresh_token},
        )

    def get_current_user(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/me",
            access_token=access_token,
        )

    def get_binance_credentials_status(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/me/binance-credentials/status",
            access_token=access_token,
        )

    def save_binance_credentials(
        self,
        *,
        access_token: str,
        api_key: str,
        api_secret: str,
        password_confirmation: str,
    ) -> ApiResponse:
        return self._request(
            "PUT",
            f"{API_PREFIX}/users/me/binance-credentials",
            json_body={
                "api_key": api_key,
                "api_secret": api_secret,
                "password_confirmation": password_confirmation,
            },
            access_token=access_token,
        )

    def delete_binance_credentials(self, access_token: str) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/users/me/binance-credentials",
            access_token=access_token,
        )

    def verify_exchange_credentials(
        self,
        access_token: str,
        *,
        credential_id: str = "binance_spot_testnet",
    ) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/users/me/exchange-credentials/{credential_id}/verify",
            access_token=access_token,
        )

    def get_testnet_ping(self, access_token: str) -> ApiResponse:
        return self._request("GET", f"{API_PREFIX}/binance-testnet/ping", access_token=access_token)

    def get_testnet_overview(self, access_token: str, *, symbol: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/overview",
            query_params={"symbol": symbol},
            access_token=access_token,
        )

    def get_testnet_account(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET", f"{API_PREFIX}/binance-testnet/account", access_token=access_token
        )

    def get_testnet_balances(self, access_token: str, *, non_zero: bool = True) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/balances",
            query_params={"non_zero": str(non_zero).lower()},
            access_token=access_token,
        )

    def get_testnet_ticker(self, access_token: str, *, symbol: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/ticker/{symbol}",
            access_token=access_token,
        )

    def get_testnet_symbol_info(self, access_token: str, *, symbol: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/symbols/{symbol}",
            access_token=access_token,
        )

    def get_testnet_open_orders(
        self, access_token: str, *, symbol: str | None = None
    ) -> ApiResponse:
        query_params = {"symbol": symbol} if symbol else None
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/open-orders",
            query_params=query_params,
            access_token=access_token,
        )

    def get_testnet_all_orders(
        self, access_token: str, *, symbol: str, limit: int = 50
    ) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/all-orders/{symbol}",
            query_params={"limit": str(limit)},
            access_token=access_token,
        )

    def get_testnet_my_trades(
        self, access_token: str, *, symbol: str, limit: int = 50
    ) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/binance-testnet/my-trades/{symbol}",
            query_params={"limit": str(limit)},
            access_token=access_token,
        )

    def test_testnet_order(self, access_token: str, payload: Mapping[str, Any]) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/binance-testnet/orders/test",
            json_body=payload,
            access_token=access_token,
        )

    def place_testnet_order(self, access_token: str, payload: Mapping[str, Any]) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/binance-testnet/orders",
            json_body=payload,
            access_token=access_token,
        )

    def cancel_testnet_order(self, access_token: str, payload: Mapping[str, Any]) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/binance-testnet/orders",
            json_body=payload,
            access_token=access_token,
        )

    def cancel_testnet_open_orders(self, access_token: str, *, symbol: str) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/binance-testnet/open-orders/{symbol}",
            access_token=access_token,
        )

    def list_bot_templates(self, access_token: str | None = None) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/bot-templates",
            access_token=access_token,
        )

    def get_bot_template(self, template_id: str, access_token: str | None = None) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/bot-templates/{template_id}",
            access_token=access_token,
        )

    def create_user_bot(
        self, access_token: str, *, template_id: str, quote_order_quantity: float | None = None
    ) -> ApiResponse:
        json_body: dict[str, object] = {"bot_template_id": template_id}
        if quote_order_quantity is not None:
            json_body["quote_order_quantity"] = quote_order_quantity
        return self._request(
            "POST",
            f"{API_PREFIX}/user-bots",
            json_body=json_body,
            access_token=access_token,
        )

    def list_user_bots(self, access_token: str) -> ApiResponse:
        return self._request("GET", f"{API_PREFIX}/user-bots", access_token=access_token)

    def start_user_bot(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/user-bots/{instance_id}/start",
            access_token=access_token,
        )

    def pause_user_bot(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/user-bots/{instance_id}/pause",
            access_token=access_token,
        )

    def stop_user_bot(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/user-bots/{instance_id}/stop",
            access_token=access_token,
        )

    def list_user_bot_decisions(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/{instance_id}/decisions",
            access_token=access_token,
        )

    def list_user_bot_orders(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/{instance_id}/orders",
            access_token=access_token,
        )

    def list_user_bot_trades(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/{instance_id}/trades",
            access_token=access_token,
        )

    def get_user_bot_position(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/{instance_id}/position",
            access_token=access_token,
        )

    def get_user_bot_performance(self, access_token: str, *, instance_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/{instance_id}/performance",
            access_token=access_token,
        )

    def get_user_bot_performance_summary(
        self,
        access_token: str,
        *,
        period_days: int = 30,
        bot_id: str | None = None,
        model_name: str | None = None,
    ) -> ApiResponse:
        query_params: dict[str, str] = {"period_days": str(period_days)}
        if bot_id:
            query_params["bot_id"] = bot_id
        if model_name:
            query_params["model_name"] = model_name
        return self._request(
            "GET",
            f"{API_PREFIX}/user-bots/performance-summary",
            query_params=query_params,
            access_token=access_token,
        )

    def list_users(
        self,
        access_token: str,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        is_active: bool | None = None,
        is_admin: bool | None = None,
    ) -> ApiResponse:
        query_params: dict[str, str] = {"skip": str(skip), "limit": str(limit)}
        if search:
            query_params["search"] = search
        if is_active is not None:
            query_params["is_active"] = str(is_active).lower()
        if is_admin is not None:
            query_params["is_admin"] = str(is_admin).lower()
        return self._request(
            "GET",
            f"{API_PREFIX}/users/",
            query_params=query_params,
            access_token=access_token,
        )

    def get_user_by_id(self, access_token: str, *, user_id: str) -> ApiResponse:
        return self._request("GET", f"{API_PREFIX}/users/{user_id}", access_token=access_token)

    def activate_user(self, access_token: str, *, user_id: str) -> ApiResponse:
        return self._request(
            "POST", f"{API_PREFIX}/users/{user_id}/activate", access_token=access_token
        )

    def deactivate_user(self, access_token: str, *, user_id: str) -> ApiResponse:
        return self._request(
            "POST", f"{API_PREFIX}/users/{user_id}/deactivate", access_token=access_token
        )

    def make_user_admin(self, access_token: str, *, user_id: str) -> ApiResponse:
        return self._request(
            "POST", f"{API_PREFIX}/users/{user_id}/make-admin", access_token=access_token
        )

    def remove_user_admin(self, access_token: str, *, user_id: str) -> ApiResponse:
        return self._request(
            "POST", f"{API_PREFIX}/users/{user_id}/remove-admin", access_token=access_token
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        form_body: Mapping[str, str] | None = None,
        query_params: Mapping[str, str] | None = None,
        access_token: str | None = None,
    ) -> ApiResponse:
        url = self._build_url(path, query_params)
        body: bytes | None = None
        headers = {"Accept": "application/json"}

        if json_body is not None:
            body = json.dumps(dict(json_body)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif form_body is not None:
            body = parse.urlencode(dict(form_body)).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        http_request = request.Request(url=url, data=body, headers=headers, method=method.upper())

        try:
            with request.urlopen(http_request, timeout=self.timeout) as response:
                raw_payload = response.read().decode("utf-8")
                return ApiResponse(
                    status_code=response.status,
                    data=self._decode_payload(raw_payload),
                    headers=dict(response.headers.items()),
                )
        except error.HTTPError as exc:
            raw_payload = exc.read().decode("utf-8")
            return ApiResponse(
                status_code=exc.code,
                data=self._decode_payload(raw_payload),
                headers=dict(exc.headers.items()),
            )
        except error.URLError as exc:
            return ApiResponse(status_code=0, error=f"Connexion API impossible: {exc.reason}")
        except Exception as exc:  # pragma: no cover
            return ApiResponse(status_code=0, error=f"Erreur client auth: {exc}")

    def _build_url(self, path: str, query_params: Mapping[str, str] | None = None) -> str:
        url = f"{self.base_url}{path}"
        if not query_params:
            return url
        return f"{url}?{parse.urlencode(dict(query_params))}"

    @staticmethod
    def _decode_payload(raw_payload: str) -> Any:
        if not raw_payload:
            return None
        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            return raw_payload
