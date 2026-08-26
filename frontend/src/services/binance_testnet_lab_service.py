"""Frontend service for the temporary Binance Spot Testnet lab."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from services.auth_api_client import ApiResponse, AuthApiClient
from services.base import ServiceError
from state.session import get_access_token, get_refresh_token, set_auth_tokens


class BinanceTestnetLabService:
    def __init__(self, client: AuthApiClient | None = None) -> None:
        self.client = client or AuthApiClient()

    def has_backend_session(self) -> bool:
        return bool(get_access_token())

    def ping(self) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_ping(token))

    def overview(self, symbol: str) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_overview(token, symbol=symbol))

    def account(self) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_account(token))

    def balances(self, *, non_zero: bool = True) -> Any:
        return self._unwrap(
            lambda token: self.client.get_testnet_balances(token, non_zero=non_zero)
        )

    def ticker(self, symbol: str) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_ticker(token, symbol=symbol))

    def symbol_info(self, symbol: str) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_symbol_info(token, symbol=symbol))

    def open_orders(self, symbol: str | None = None) -> Any:
        return self._unwrap(lambda token: self.client.get_testnet_open_orders(token, symbol=symbol))

    def all_orders(self, symbol: str, limit: int = 50) -> Any:
        return self._unwrap(
            lambda token: self.client.get_testnet_all_orders(token, symbol=symbol, limit=limit)
        )

    def my_trades(self, symbol: str, limit: int = 50) -> Any:
        return self._unwrap(
            lambda token: self.client.get_testnet_my_trades(token, symbol=symbol, limit=limit)
        )

    def test_order(self, payload: Mapping[str, Any]) -> Any:
        return self._unwrap(lambda token: self.client.test_testnet_order(token, payload))

    def place_order(self, payload: Mapping[str, Any]) -> Any:
        return self._unwrap(lambda token: self.client.place_testnet_order(token, payload))

    def cancel_order(self, payload: Mapping[str, Any]) -> Any:
        return self._unwrap(lambda token: self.client.cancel_testnet_order(token, payload))

    def cancel_open_orders(self, symbol: str) -> Any:
        return self._unwrap(
            lambda token: self.client.cancel_testnet_open_orders(token, symbol=symbol)
        )

    def _unwrap(self, request_fn: Callable[[str], ApiResponse]) -> Any:
        response = self._request_with_auth_refresh(request_fn)
        if not response.success:
            raise ServiceError(self._extract_error_message(response))
        return response.data

    def _request_with_auth_refresh(
        self,
        request_fn: Callable[[str], ApiResponse],
    ) -> ApiResponse:
        access_token = get_access_token()
        if not access_token:
            return ApiResponse(status_code=0, error="Session backend requise.")

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
    def _extract_error_message(response: ApiResponse) -> str:
        if response.error:
            return response.error
        payload = response.data
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, dict):
                message = detail.get("message")
                code = detail.get("binance_code")
                if message and code is not None:
                    return f"Binance {code}: {message}"
                if message:
                    return str(message)
            if isinstance(detail, str) and detail:
                return detail
            message = payload.get("message")
            if isinstance(message, str) and message:
                return message
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        if response.status_code == 0:
            return "API Binance Testnet indisponible."
        return f"Erreur backend ({response.status_code})."
