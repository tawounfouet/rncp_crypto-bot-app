"""Service marché public - connecté au backend réel, aucune authentification requise."""

from __future__ import annotations

from schemas.market import ExchangeOption, PublicKline, PublicPrice
from services.api_client import BackendApiClient
from services.base import ServiceError
from utils.api_errors import extract_error as _extract_error
from utils.dates import parse_dt_or_now
from utils.numeric import to_float as _float


class MarketService:
    def __init__(self, client: BackendApiClient | None = None) -> None:
        self.client = client or BackendApiClient()

    def list_exchanges(self) -> list[ExchangeOption]:
        response = self.client.get_public_exchanges()
        if not response.success:
            raise ServiceError(f"Impossible de charger les plateformes: {_extract_error(response)}")
        data = response.data or {}
        return [ExchangeOption(**item) for item in data.get("data", [])]

    def get_prices(
        self, exchange: str, symbols: list[str] | None = None
    ) -> tuple[list[PublicPrice], list[str]]:
        response = self.client.get_public_prices(exchange=exchange, symbols=symbols)
        if not response.success:
            raise ServiceError(f"Impossible de charger les prix: {_extract_error(response)}")
        data = response.data or {}
        prices = [
            PublicPrice(
                symbol=item.get("symbol", ""),
                exchange=item.get("exchange", exchange),
                price=_float(item.get("price")),
                as_of=parse_dt_or_now(item.get("as_of")),
            )
            for item in data.get("data", [])
        ]
        warnings = data.get("warnings", [])
        return prices, warnings

    def get_klines(
        self, exchange, symbol, interval="1h", limit=24
    ) -> tuple[list[PublicKline], list[str]]:
        response = self.client.get_public_klines(
            exchange=exchange, symbol=symbol, interval=interval, limit=limit
        )
        if not response.success:
            raise ServiceError(f"Impossible de charger les klines: {_extract_error(response)}")
        data = response.data or {}
        klines = [
            PublicKline(
                symbol=item.get("symbol", ""),
                exchange=item.get("exchange", exchange),
                interval=item.get("interval", interval),
                open_time=parse_dt_or_now(item.get("open_time")),
                open=_float(item.get("open")),
                high=_float(item.get("high")),
                low=_float(item.get("low")),
                close=_float(item.get("close")),
                volume=_float(item.get("volume")),
            )
            for item in data.get("data", [])
        ]
        warnings = data.get("warnings", [])
        return klines, warnings
