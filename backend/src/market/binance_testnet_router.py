"""Temporary Binance Spot Testnet lab routes."""

from __future__ import annotations

from typing import Any

from auth.dependencies import get_current_user
from auth.models import User
from fastapi import APIRouter, Depends, Path, Query

from market.binance_testnet_schemas import BinanceTestnetCancelOrderRequest, BinanceTestnetOrderRequest
from market.binance_testnet_service import BinanceTestnetService

router = APIRouter(prefix="/binance-testnet", tags=["Binance Testnet Lab"])


def get_binance_testnet_service() -> BinanceTestnetService:
    return BinanceTestnetService()


@router.get("/ping")
async def ping_testnet(
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.ping()


@router.get("/overview")
async def get_overview(
    symbol: str = Query("BTCUSDT", min_length=3, max_length=20),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.overview(current_user.id, symbol)


@router.get("/account")
async def get_account(
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.account(current_user.id)


@router.get("/balances")
async def get_balances(
    non_zero: bool = Query(True),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> list[dict[str, Any]]:
    return service.balances(current_user.id, non_zero=non_zero)


@router.get("/ticker/{symbol}")
async def get_ticker(
    symbol: str = Path(..., min_length=3, max_length=20),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.ticker(symbol)


@router.get("/symbols/{symbol}")
async def get_symbol_info(
    symbol: str = Path(..., min_length=3, max_length=20),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.symbol_info(symbol)


@router.get("/open-orders")
async def get_open_orders(
    symbol: str | None = Query(None, min_length=3, max_length=20),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> list[dict[str, Any]]:
    return service.open_orders(current_user.id, symbol)


@router.get("/all-orders/{symbol}")
async def get_all_orders(
    symbol: str = Path(..., min_length=3, max_length=20),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> list[dict[str, Any]]:
    return service.all_orders(current_user.id, symbol, limit=limit)


@router.get("/my-trades/{symbol}")
async def get_my_trades(
    symbol: str = Path(..., min_length=3, max_length=20),
    limit: int = Query(50, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> list[dict[str, Any]]:
    return service.my_trades(current_user.id, symbol, limit=limit)


@router.post("/orders/test")
async def test_order(
    order: BinanceTestnetOrderRequest,
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.test_order(current_user.id, order)


@router.post("/orders")
async def place_order(
    order: BinanceTestnetOrderRequest,
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.place_order(current_user.id, order)


@router.delete("/orders")
async def cancel_order(
    payload: BinanceTestnetCancelOrderRequest,
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> dict[str, Any]:
    return service.cancel_order(current_user.id, payload)


@router.delete("/open-orders/{symbol}")
async def cancel_open_orders(
    symbol: str = Path(..., min_length=3, max_length=20),
    current_user: User = Depends(get_current_user),
    service: BinanceTestnetService = Depends(get_binance_testnet_service),
) -> list[dict[str, Any]]:
    return service.cancel_open_orders(current_user.id, symbol)
