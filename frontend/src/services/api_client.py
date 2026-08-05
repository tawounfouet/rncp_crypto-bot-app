"""Client HTTP unifie pour tous les endpoints du backend."""

from __future__ import annotations

from typing import Any

from services.auth_api_client import ApiResponse, AuthApiClient

API_PREFIX = "/api/v1"


class BackendApiClient(AuthApiClient):
    """Extension de AuthApiClient avec tous les endpoints metier."""

    # ─── Users ───────────────────────────────────────────────────────────────

    def update_user(
        self,
        access_token: str,
        *,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {}
        if first_name is not None:
            payload["first_name"] = first_name
        if last_name is not None:
            payload["last_name"] = last_name
        if email is not None:
            payload["email"] = email
        return self._request(
            "PUT",
            f"{API_PREFIX}/users/me",
            json_body=payload,
            access_token=access_token,
        )

    def get_user_settings(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/me/settings",
            access_token=access_token,
        )

    def update_user_settings(
        self,
        access_token: str,
        *,
        binance_api_key: str | None = None,
        binance_api_secret: str | None = None,
        theme: str | None = None,
        risk_profile: str | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {}
        if binance_api_key is not None:
            payload["binance_api_key"] = binance_api_key
        if binance_api_secret is not None:
            payload["binance_api_secret"] = binance_api_secret
        if theme is not None:
            payload["theme"] = theme
        if risk_profile is not None:
            payload["risk_profile"] = risk_profile
        return self._request(
            "PUT",
            f"{API_PREFIX}/users/me/settings",
            json_body=payload,
            access_token=access_token,
        )

    def list_users(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/",
            access_token=access_token,
        )

    def get_user_by_id(self, access_token: str, user_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/users/{user_id}",
            access_token=access_token,
        )

    def activate_user(self, access_token: str, user_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/users/{user_id}/activate",
            access_token=access_token,
        )

    def deactivate_user(self, access_token: str, user_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/users/{user_id}/deactivate",
            access_token=access_token,
        )

    # ─── Trading ─────────────────────────────────────────────────────────────

    def get_portfolio(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/trading/portfolio",
            access_token=access_token,
        )

    def list_orders(
        self,
        access_token: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> ApiResponse:
        params: dict[str, str] = {"limit": str(limit)}
        if status:
            params["status"] = status
        return self._request(
            "GET",
            f"{API_PREFIX}/trading/orders",
            query_params=params,
            access_token=access_token,
        )

    def cancel_order(self, access_token: str, order_id: str) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/trading/orders/{order_id}",
            access_token=access_token,
        )

    def get_trading_stats(self, access_token: str, period: str = "30d") -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/trading/stats",
            query_params={"period": period},
            access_token=access_token,
        )

    def list_transactions(
        self,
        access_token: str,
        *,
        limit: int = 100,
    ) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/trading/transactions",
            query_params={"limit": str(limit)},
            access_token=access_token,
        )

    # ─── Strategies ──────────────────────────────────────────────────────────

    def create_strategy(
        self,
        access_token: str,
        *,
        name: str,
        strategy_type: str,
        parameters: dict,
        description: str | None = None,
    ) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/strategies/",
            json_body={
                "name": name,
                "strategy_type": strategy_type,
                "parameters": parameters,
                "description": description,
                "asset_class": "crypto",
                "is_public": False,
            },
            access_token=access_token,
        )

    def delete_strategy(self, access_token: str, strategy_id: str) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/strategies/{strategy_id}",
            access_token=access_token,
        )

    def list_strategies(self, access_token: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/strategies/",
            access_token=access_token,
        )

    def get_strategy(self, access_token: str, strategy_id: str) -> ApiResponse:
        return self._request(
            "GET",
            f"{API_PREFIX}/strategies/{strategy_id}",
            access_token=access_token,
        )

    def update_strategy(
        self,
        access_token: str,
        strategy_id: str,
        payload: dict[str, Any],
    ) -> ApiResponse:
        return self._request(
            "PUT",
            f"{API_PREFIX}/strategies/{strategy_id}",
            json_body=payload,
            access_token=access_token,
        )

    def list_deployments(
        self,
        access_token: str,
        *,
        active_only: bool = False,
    ) -> ApiResponse:
        params: dict[str, str] = {}
        if active_only:
            params["active_only"] = "true"
        return self._request(
            "GET",
            f"{API_PREFIX}/strategies/deployments/",
            query_params=params or None,
            access_token=access_token,
        )

    def deploy_strategy(
        self,
        access_token: str,
        strategy_id: str,
        *,
        exchange: str,
        symbol: str,
        timeframe: str,
        amount: float,
        is_paper: bool = True,
    ) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/strategies/{strategy_id}/deploy",
            json_body={
                "strategy_id": strategy_id,
                "exchange": exchange,
                "symbol": symbol,
                "timeframe": timeframe,
                "amount": str(amount),
                "is_paper": is_paper,
            },
            access_token=access_token,
        )

    def stop_deployment(self, access_token: str, deployment_id: str) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/strategies/deployments/{deployment_id}/stop",
            access_token=access_token,
        )

    # ─── API Credentials (multi-key) ────────────────────────────────────────

    def list_api_credentials(self, access_token: str) -> ApiResponse:
        return self._request("GET", f"{API_PREFIX}/users/me/api-keys", access_token=access_token)

    def add_api_credential(
        self,
        access_token: str,
        *,
        label: str,
        exchange: str,
        api_key: str,
        api_secret: str,
    ) -> ApiResponse:
        return self._request(
            "POST",
            f"{API_PREFIX}/users/me/api-keys",
            json_body={
                "label": label,
                "exchange": exchange,
                "api_key": api_key,
                "api_secret": api_secret,
            },
            access_token=access_token,
        )

    def set_primary_api_credential(self, access_token: str, key_id: str) -> ApiResponse:
        return self._request(
            "PUT",
            f"{API_PREFIX}/users/me/api-keys/{key_id}/primary",
            access_token=access_token,
        )

    def delete_api_credential(self, access_token: str, key_id: str) -> ApiResponse:
        return self._request(
            "DELETE",
            f"{API_PREFIX}/users/me/api-keys/{key_id}",
            access_token=access_token,
        )

    # ─── Market data ─────────────────────────────────────────────────────────

    def get_market_coverage(self, access_token: str) -> ApiResponse:
        """GET /market/data/coverage — résumé des données OHLCV stockées en base."""
        return self._request(
            "GET",
            f"{API_PREFIX}/market/data/coverage",
            access_token=access_token,
        )

    def insert_market_data(
        self,
        access_token: str,
        *,
        symbol: str,
        interval: str,
        start_time: str,
        end_time: str,
        limit: int = 1000,
    ) -> ApiResponse:
        """POST /market/data/insert — importe les klines Binance en base (upsert)."""
        return self._request(
            "POST",
            f"{API_PREFIX}/market/data/insert",
            json_body={
                "symbol": symbol,
                "interval": interval,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
            access_token=access_token,
        )

    # ─── Backtesting ─────────────────────────────────────────────────────────

    def run_backtest(
        self,
        access_token: str,
        *,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_balance: float,
        parameters: dict | None = None,
    ) -> ApiResponse:
        payload: dict[str, Any] = {
            "strategy_id": strategy_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "initial_balance": str(initial_balance),
        }
        if parameters:
            payload["parameters"] = parameters
        return self._request(
            "POST",
            f"{API_PREFIX}/strategies/backtests",
            json_body=payload,
            access_token=access_token,
        )

    def list_backtests(self, access_token: str) -> ApiResponse:
        return self._request("GET", f"{API_PREFIX}/strategies/backtests", access_token=access_token)

    def get_backtest(self, access_token: str, backtest_id: str) -> ApiResponse:
        return self._request(
            "GET", f"{API_PREFIX}/strategies/backtests/{backtest_id}", access_token=access_token
        )
