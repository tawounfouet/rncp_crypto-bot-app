"""Temporary Binance Spot Testnet integration service.

This module is intentionally isolated from the production trading roadmap. It
only talks to Binance Spot Testnet and only uses credentials stored for the
authenticated user.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import requests
from auth.models import UserExchangeCredential, UserSettings
from fastapi import HTTPException, status
from shared.database.connection import get_db_session

from market.binance_testnet_schemas import BinanceTestnetCancelOrderRequest, BinanceTestnetOrderRequest

TESTNET_API_BASE_URL = "https://testnet.binance.vision/api"
TESTNET_CREDENTIAL_KEY = "binance_spot_testnet"
LEGACY_CREDENTIAL_KEY = "binance"
DEFAULT_RECV_WINDOW = 5000


class BinanceTestnetService:
    """Signed REST client for Binance Spot Testnet."""

    def __init__(self, base_url: str = TESTNET_API_BASE_URL, timeout_seconds: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def ping(self) -> dict[str, Any]:
        server_time = self._public_request("GET", "/v3/time")
        return {
            "mode": "SPOT_TESTNET",
            "base_url": self.base_url,
            "server_time": server_time.get("serverTime"),
        }

    def account(self, user_id: str) -> dict[str, Any]:
        account = self._signed_request(user_id, "GET", "/v3/account")
        account["balances"] = self._sort_balances(account.get("balances", []), non_zero=False)
        return account

    def balances(self, user_id: str, *, non_zero: bool = True) -> list[dict[str, Any]]:
        account = self.account(user_id)
        return self._sort_balances(account.get("balances", []), non_zero=non_zero)

    def ticker(self, symbol: str) -> dict[str, Any]:
        return self._public_request("GET", "/v3/ticker/24hr", {"symbol": self._symbol(symbol)})

    def klines(self, symbol: str, interval: str, *, limit: int = 120) -> list[list[Any]]:
        payload = self._public_request(
            "GET",
            "/v3/klines",
            {
                "symbol": self._symbol(symbol),
                "interval": interval,
                "limit": max(10, min(limit, 1000)),
            },
        )
        return payload if isinstance(payload, list) else []

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        payload = self._public_request("GET", "/v3/exchangeInfo", {"symbol": self._symbol(symbol)})
        symbols = payload.get("symbols", [])
        if not symbols:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Symbol not found on Binance Testnet")
        return symbols[0]

    def open_orders(self, user_id: str, symbol: str | None = None) -> list[dict[str, Any]]:
        params = {"symbol": self._symbol(symbol)} if symbol else {}
        payload = self._signed_request(user_id, "GET", "/v3/openOrders", params)
        return payload if isinstance(payload, list) else []

    def all_orders(self, user_id: str, symbol: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self._signed_request(
            user_id,
            "GET",
            "/v3/allOrders",
            {"symbol": self._symbol(symbol), "limit": max(1, min(limit, 500))},
        )
        return payload if isinstance(payload, list) else []

    def my_trades(self, user_id: str, symbol: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self._signed_request(
            user_id,
            "GET",
            "/v3/myTrades",
            {"symbol": self._symbol(symbol), "limit": max(1, min(limit, 1000))},
        )
        return payload if isinstance(payload, list) else []

    def test_order(self, user_id: str, order: BinanceTestnetOrderRequest) -> dict[str, Any]:
        self._signed_request(user_id, "POST", "/v3/order/test", self._order_params(order))
        return {"accepted": True, "mode": "TEST_ORDER", "symbol": self._symbol(order.symbol)}

    def place_order(self, user_id: str, order: BinanceTestnetOrderRequest) -> dict[str, Any]:
        return self._signed_request(user_id, "POST", "/v3/order", self._order_params(order))

    def cancel_order(self, user_id: str, payload: BinanceTestnetCancelOrderRequest) -> dict[str, Any]:
        params: dict[str, Any] = {"symbol": self._symbol(payload.symbol)}
        if payload.order_id is not None:
            params["orderId"] = payload.order_id
        if payload.orig_client_order_id:
            params["origClientOrderId"] = payload.orig_client_order_id
        return self._signed_request(user_id, "DELETE", "/v3/order", params)

    def cancel_open_orders(self, user_id: str, symbol: str) -> list[dict[str, Any]]:
        payload = self._signed_request(user_id, "DELETE", "/v3/openOrders", {"symbol": self._symbol(symbol)})
        return payload if isinstance(payload, list) else []

    def overview(self, user_id: str, symbol: str = "BTCUSDT") -> dict[str, Any]:
        account = self.account(user_id)
        return {
            "mode": "SPOT_TESTNET",
            "server": self.ping(),
            "account_type": account.get("accountType"),
            "can_trade": account.get("canTrade"),
            "can_withdraw": account.get("canWithdraw"),
            "can_deposit": account.get("canDeposit"),
            "balances": self._sort_balances(account.get("balances", []), non_zero=True),
            "ticker": self.ticker(symbol),
            "open_orders": self.open_orders(user_id, symbol),
        }

    def _signed_request(
        self,
        user_id: str,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        api_key, api_secret = self._credentials_for_user(user_id)
        payload = self._clean_params(params or {})
        payload["timestamp"] = int(time.time() * 1000)
        payload["recvWindow"] = DEFAULT_RECV_WINDOW
        query = urlencode(payload)
        signature = hmac.new(api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        payload["signature"] = signature
        return self._request(method, path, payload, api_key=api_key)

    def _public_request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request(method, path, self._clean_params(params or {}))

    def _request(self, method: str, path: str, params: dict[str, Any], api_key: str | None = None) -> Any:
        headers = {"Accept": "application/json"}
        if api_key:
            headers["X-MBX-APIKEY"] = api_key

        try:
            response = requests.request(
                method=method.upper(),
                url=f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Binance Testnet is unreachable: {exc}",
            ) from exc

        data = self._decode_response(response)
        if response.status_code >= 400:
            detail = self._safe_error_detail(data, path)
            raise HTTPException(status_code=response.status_code, detail=detail)
        return data

    @staticmethod
    def _decode_response(response: requests.Response) -> Any:
        if not response.text:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"message": response.text}

    @staticmethod
    def _safe_error_detail(data: Any, path: str) -> dict[str, Any]:
        if isinstance(data, dict):
            return {
                "binance_code": data.get("code"),
                "message": data.get("msg") or data.get("message") or "Binance Testnet request failed",
                "endpoint": path,
            }
        return {"message": "Binance Testnet request failed", "endpoint": path}

    def _credentials_for_user(self, user_id: str) -> tuple[str, str]:
        with get_db_session() as session:
            credential = (
                session.query(UserExchangeCredential)
                .filter(
                    UserExchangeCredential.user_id == user_id,
                    UserExchangeCredential.exchange == "binance",
                    UserExchangeCredential.environment == "testnet",
                    UserExchangeCredential.is_active.is_(True),
                )
                .order_by(UserExchangeCredential.updated_at.desc())
                .first()
            )
            if credential:
                api_key = credential.get_api_key()
                api_secret = credential.get_api_secret()
                if api_key and api_secret:
                    return api_key, api_secret

            settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
            if not settings:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Binance Testnet credentials are not configured.",
                )
            api_key = settings.get_api_key(TESTNET_CREDENTIAL_KEY) or settings.get_api_key(LEGACY_CREDENTIAL_KEY)
            api_secret = settings.get_api_secret(TESTNET_CREDENTIAL_KEY) or settings.get_api_secret(
                LEGACY_CREDENTIAL_KEY
            )

        if not api_key or not api_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Binance Testnet credentials are not configured.",
            )
        return api_key, api_secret

    @staticmethod
    def _order_params(order: BinanceTestnetOrderRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": BinanceTestnetService._symbol(order.symbol),
            "side": order.side,
            "type": order.order_type,
        }
        if order.quantity is not None:
            params["quantity"] = BinanceTestnetService._decimal_to_str(order.quantity)
        if order.quote_order_quantity is not None:
            params["quoteOrderQty"] = BinanceTestnetService._decimal_to_str(order.quote_order_quantity)
        if order.order_type == "LIMIT":
            params["timeInForce"] = order.time_in_force
            params["price"] = BinanceTestnetService._decimal_to_str(order.price)
        if order.client_order_id:
            params["newClientOrderId"] = order.client_order_id
        return params

    @staticmethod
    def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in params.items() if value is not None and value != ""}

    @staticmethod
    def _symbol(symbol: str | None) -> str:
        return (symbol or "BTCUSDT").strip().upper()

    @staticmethod
    def _decimal_to_str(value: Decimal | None) -> str:
        if value is None:
            return ""
        return format(value.normalize(), "f")

    @staticmethod
    def _sort_balances(balances: Any, *, non_zero: bool) -> list[dict[str, Any]]:
        if not isinstance(balances, list):
            return []
        clean_balances = []
        for balance in balances:
            if not isinstance(balance, dict):
                continue
            free = Decimal(str(balance.get("free", "0")))
            locked = Decimal(str(balance.get("locked", "0")))
            if non_zero and free == 0 and locked == 0:
                continue
            clean_balances.append(
                {
                    "asset": balance.get("asset"),
                    "free": str(free),
                    "locked": str(locked),
                    "total": str(free + locked),
                }
            )
        return sorted(clean_balances, key=lambda item: item["asset"] or "")
