"""Schemas for the temporary Binance Spot Testnet lab."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

OrderSide = Literal["BUY", "SELL"]
OrderType = Literal["MARKET", "LIMIT"]
TimeInForce = Literal["GTC", "IOC", "FOK"]


class BinanceTestnetOrderRequest(BaseModel):
    """Payload for creating or validating a Binance Spot Testnet order."""

    symbol: str = Field("BTCUSDT", min_length=3, max_length=20)
    side: OrderSide
    order_type: OrderType = "LIMIT"
    quantity: Decimal | None = Field(None, gt=0)
    quote_order_quantity: Decimal | None = Field(None, gt=0)
    price: Decimal | None = Field(None, gt=0)
    time_in_force: TimeInForce = "GTC"
    client_order_id: str | None = Field(None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_order_shape(self) -> BinanceTestnetOrderRequest:
        if self.order_type == "LIMIT":
            if self.quantity is None:
                raise ValueError("quantity is required for LIMIT orders")
            if self.price is None:
                raise ValueError("price is required for LIMIT orders")
        if self.order_type == "MARKET" and self.quantity is None and self.quote_order_quantity is None:
            raise ValueError("quantity or quote_order_quantity is required for MARKET orders")
        return self


class BinanceTestnetCancelOrderRequest(BaseModel):
    """Payload for cancelling one Binance Spot Testnet order."""

    symbol: str = Field(..., min_length=3, max_length=20)
    order_id: int | None = Field(None, gt=0)
    orig_client_order_id: str | None = Field(None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_cancel_target(self) -> BinanceTestnetCancelOrderRequest:
        if self.order_id is None and not self.orig_client_order_id:
            raise ValueError("order_id or orig_client_order_id is required")
        return self
