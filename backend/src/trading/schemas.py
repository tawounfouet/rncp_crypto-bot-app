"""
Trading-related Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for orders, transactions, and trading operations.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from enum import Enum

from shared.schemas.common import BaseResponse


class OrderTypeEnum(str, Enum):
    """Order types compatible with Binance API."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


class OrderSideEnum(str, Enum):
    """Order sides."""

    BUY = "BUY"
    SELL = "SELL"


class OrderStatusEnum(str, Enum):
    """Order statuses compatible with Binance API."""

    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    PENDING_CANCEL = "PENDING_CANCEL"


class TimeInForceEnum(str, Enum):
    """Time in force options."""

    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill


class TransactionTypeEnum(str, Enum):
    """Transaction types."""

    TRADE = "TRADE"
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    FEE = "FEE"


class TransactionDirectionEnum(str, Enum):
    """Transaction directions."""

    IN = "IN"
    OUT = "OUT"


class PositionEnum(str, Enum):
    """Position types."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


# Order Creation and Management
class OrderCreate(BaseModel):
    """Schema for creating a new order."""

    deployment_id: str
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    order_type: OrderTypeEnum
    side: OrderSideEnum
    quantity: Decimal = Field(..., gt=0, description="Order quantity")
    price: Optional[Decimal] = Field(None, gt=0, description="Price for limit orders")
    stop_price: Optional[Decimal] = Field(None, gt=0, description="Stop price for stop orders")
    time_in_force: Optional[TimeInForceEnum] = Field(None, description="Time in force")
    quote_order_quantity: Optional[Decimal] = Field(None, gt=0, description="Quote asset quantity")

    class Config:
        json_schema_extra = {
            "example": {
                "deployment_id": "deploy-123",
                "symbol": "BTCUSDT",
                "order_type": "LIMIT",
                "side": "BUY",
                "quantity": "0.001",
                "price": "45000.00",
                "time_in_force": "GTC",
            }
        }


class OrderUpdate(BaseModel):
    """Schema for updating an order."""

    status: Optional[OrderStatusEnum] = None
    executed_quantity: Optional[Decimal] = None
    cumulative_quote_quantity: Optional[Decimal] = None


# Order Responses
class OrderFill(BaseModel):
    """Order fill information."""

    id: str
    trade_id: str
    price: Decimal
    quantity: Decimal
    commission: Decimal
    commission_asset: str
    timestamp: datetime
    is_buyer: bool
    is_maker: bool

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """Order response with all details."""

    id: str
    deployment_id: str
    user_id: str
    exchange: str
    exchange_order_id: Optional[str]
    client_order_id: Optional[str]
    symbol: str
    order_type: OrderTypeEnum
    side: OrderSideEnum
    time_in_force: Optional[TimeInForceEnum]
    quantity: Decimal
    executed_quantity: Decimal
    quote_order_quantity: Optional[Decimal]
    cumulative_quote_quantity: Optional[Decimal]
    price: Optional[Decimal]
    stop_price: Optional[Decimal]
    status: OrderStatusEnum
    transact_time: Optional[datetime]
    working_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    fills: List[OrderFill] = []

    class Config:
        from_attributes = True


class OrderSummary(BaseModel):
    """Simplified order information."""

    id: str
    symbol: str
    order_type: OrderTypeEnum
    side: OrderSideEnum
    quantity: Decimal
    executed_quantity: Decimal
    price: Optional[Decimal]
    status: OrderStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True


# Transaction Schemas
class TransactionCreate(BaseModel):
    """Schema for creating a transaction."""

    exchange: str
    transaction_type: TransactionTypeEnum
    order_id: Optional[str] = None
    asset: str
    amount: Decimal = Field(..., gt=0)
    direction: TransactionDirectionEnum
    quote_asset: Optional[str] = None
    quote_amount: Optional[Decimal] = None
    price: Optional[Decimal] = None
    fee_amount: Optional[Decimal] = None
    fee_asset: Optional[str] = None
    external_id: Optional[str] = None
    description: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "exchange": "binance",
                "transaction_type": "TRADE",
                "asset": "BTC",
                "amount": "0.001",
                "direction": "IN",
                "quote_asset": "USDT",
                "quote_amount": "45.00",
                "price": "45000.00",
            }
        }


class TransactionResponse(BaseModel):
    """Transaction response."""

    id: str
    user_id: str
    exchange: str
    transaction_type: TransactionTypeEnum
    order_id: Optional[str]
    asset: str
    amount: Decimal
    direction: TransactionDirectionEnum
    quote_asset: Optional[str]
    quote_amount: Optional[Decimal]
    price: Optional[Decimal]
    fee_amount: Optional[Decimal]
    fee_asset: Optional[str]
    external_id: Optional[str]
    status: str
    description: Optional[str]
    timestamp: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionSummary(BaseModel):
    """Simplified transaction information for list views."""

    id: str
    transaction_type: TransactionTypeEnum
    asset: str
    amount: Decimal
    direction: TransactionDirectionEnum
    price: Optional[Decimal]
    timestamp: datetime

    class Config:
        from_attributes = True


# Portfolio and Balance
class AssetBalance(BaseModel):
    """Asset balance information."""

    asset: str
    total: Decimal
    available: Decimal
    locked: Decimal
    usd_value: Optional[Decimal] = None


class Portfolio(BaseModel):
    """User portfolio information."""

    user_id: str
    exchange: str
    balances: List[AssetBalance]
    total_usd_value: Decimal
    last_updated: datetime


class PositionInfo(BaseModel):
    """Trading position information."""

    deployment_id: str
    symbol: str
    position: PositionEnum
    position_size: Decimal
    entry_price: Optional[Decimal]
    current_price: Optional[Decimal]
    unrealized_pnl: Optional[Decimal]
    realized_pnl: Decimal

    class Config:
        from_attributes = True


# Trading Statistics
class TradingStats(BaseModel):
    """Trading statistics for a user or deployment."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_profit_loss: Decimal
    average_profit: Decimal
    average_loss: Decimal
    max_drawdown: Decimal
    sharpe_ratio: Optional[float] = None

    class Config:
        from_attributes = True


# Response Models
class OrderCreateResponse(BaseResponse):
    """Response after order creation."""

    order: OrderResponse


class OrderListResponse(BaseResponse):
    """Response for order list."""

    orders: List[OrderSummary]


class TransactionCreateResponse(BaseResponse):
    """Response after transaction creation."""

    transaction: TransactionResponse


class TransactionListResponse(BaseResponse):
    """Response for transaction list."""

    transactions: List[TransactionResponse]


class PortfolioResponse(BaseResponse):
    """Response for portfolio information."""

    portfolio: Portfolio


class TradingStatsResponse(BaseResponse):
    """Response for trading statistics."""

    stats: TradingStats
