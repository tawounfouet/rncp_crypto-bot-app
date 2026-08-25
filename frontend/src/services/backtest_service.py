"""Service de backtesting - appelle les endpoints /strategies/backtests."""

from __future__ import annotations

from mocks.db import MockStore
from services.api_client import BackendApiClient
from services.base import ServiceError
from state.session import get_access_token


def _extract_error(response) -> str:
    if response.error:
        return response.error
    data = response.data
    if isinstance(data, dict):
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail
    return f"Erreur backend ({response.status_code})."


def _unwrap_data(response) -> list | dict | None:
    """Extrait la liste/dict depuis les enveloppes {data: ...} ou bare list."""
    d = response.data
    if isinstance(d, dict):
        return d.get("data", d)
    return d


class BacktestService:
    def __init__(self, store: MockStore, client: BackendApiClient | None = None) -> None:
        self.store = store
        self.client = client or BackendApiClient()

    def _token(self) -> str:
        token = get_access_token()
        if not token:
            raise ServiceError("Non authentifie.")
        return token

    def run_backtest(
        self,
        strategy_id: str,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        initial_balance: float,
        parameters: dict | None = None,
    ) -> tuple[bool, str, dict | None]:
        """Lance un backtest. Retourne (success, message, result_dict|None)."""
        try:
            token = self._token()
        except ServiceError as exc:
            return False, str(exc), None

        response = self.client.run_backtest(
            token,
            strategy_id=strategy_id,
            symbol=symbol,
            timeframe=timeframe,
            start_date=start_date,
            end_date=end_date,
            initial_balance=initial_balance,
            parameters=parameters,
        )
        if not response.success:
            return False, _extract_error(response), None

        data = _unwrap_data(response)
        return True, "Backtest termine avec succes.", data if isinstance(data, dict) else None

    def list_backtests(self) -> list[dict]:
        try:
            token = self._token()
        except ServiceError:
            return []

        response = self.client.list_backtests(token)
        if not response.success:
            return []

        data = _unwrap_data(response)
        if isinstance(data, list):
            return data
        return []

    def get_backtest(self, backtest_id: str) -> dict | None:
        try:
            token = self._token()
        except ServiceError:
            return None

        response = self.client.get_backtest(token, backtest_id)
        if not response.success:
            return None

        data = _unwrap_data(response)
        return data if isinstance(data, dict) else None
