"""
Trading-related Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for orders, transactions, and trading operations.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field
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
    price: Decimal | None = Field(None, gt=0, description="Price for limit orders")
    stop_price: Decimal | None = Field(None, gt=0, description="Stop price for stop orders")
    time_in_force: TimeInForceEnum | None = Field(None, description="Time in force")
    quote_order_quantity: Decimal | None = Field(None, gt=0, description="Quote asset quantity")
    model_config = ConfigDict(
        json_schema_extra={
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
    )


class OrderUpdate(BaseModel):
    """Schema for updating an order."""

    status: OrderStatusEnum | None = None
    executed_quantity: Decimal | None = None
    cumulative_quote_quantity: Decimal | None = None


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
    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    """Order response with all details."""

    id: str
    deployment_id: str
    user_id: str
    exchange: str
    exchange_order_id: str | None = None
    client_order_id: str | None = None
    symbol: str
    order_type: OrderTypeEnum
    side: OrderSideEnum
    time_in_force: TimeInForceEnum | None = None
    quantity: Decimal
    executed_quantity: Decimal
    quote_order_quantity: Decimal | None = None
    cumulative_quote_quantity: Decimal | None = None
    price: Decimal | None = None
    stop_price: Decimal | None = None
    status: OrderStatusEnum
    transact_time: datetime | None = None
    working_time: datetime | None = None
    created_at: datetime
    updated_at: datetime
    fills: list[OrderFill] = []
    model_config = ConfigDict(from_attributes=True)


class OrderSummary(BaseModel):
    """Simplified order information."""

    id: str
    symbol: str
    order_type: OrderTypeEnum
    side: OrderSideEnum
    quantity: Decimal
    executed_quantity: Decimal
    price: Decimal | None = None
    status: OrderStatusEnum
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Transaction Schemas
class TransactionCreate(BaseModel):
    """Schema for creating a transaction."""

    exchange: str
    transaction_type: TransactionTypeEnum
    order_id: str | None = None
    asset: str
    amount: Decimal = Field(..., gt=0)
    direction: TransactionDirectionEnum
    quote_asset: str | None = None
    quote_amount: Decimal | None = None
    price: Decimal | None = None
    fee_amount: Decimal | None = None
    fee_asset: str | None = None
    external_id: str | None = None
    description: str | None = None
    model_config = ConfigDict(
        json_schema_extra={
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
    )


class TransactionResponse(BaseModel):
    """Transaction response."""

    id: str
    user_id: str
    exchange: str
    transaction_type: TransactionTypeEnum
    order_id: str | None = None
    asset: str
    amount: Decimal
    direction: TransactionDirectionEnum
    quote_asset: str | None = None
    quote_amount: Decimal | None = None
    price: Decimal | None = None
    fee_amount: Decimal | None = None
    fee_asset: str | None = None
    external_id: str | None = None
    status: str
    description: str | None = None
    timestamp: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TransactionSummary(BaseModel):
    """Simplified transaction information for list views."""

    id: str
    transaction_type: TransactionTypeEnum
    asset: str
    amount: Decimal
    direction: TransactionDirectionEnum
    price: Decimal | None = None
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)


# Portfolio and Balance
class AssetBalance(BaseModel):
    """Asset balance information."""

    asset: str
    total: Decimal
    available: Decimal
    locked: Decimal
    usd_value: Decimal | None = None


class Portfolio(BaseModel):
    """User portfolio information."""

    user_id: str
    exchange: str
    balances: list[AssetBalance]
    total_usd_value: Decimal
    last_updated: datetime


class PositionInfo(BaseModel):
    """Trading position information."""

    deployment_id: str
    symbol: str
    position: PositionEnum
    position_size: Decimal
    entry_price: Decimal | None = None
    current_price: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    realized_pnl: Decimal
    model_config = ConfigDict(from_attributes=True)


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
    sharpe_ratio: float | None = None
    model_config = ConfigDict(from_attributes=True)


# Response Models
class OrderCreateResponse(BaseResponse):
    """Response after order creation."""

    order: OrderResponse


class OrderListResponse(BaseResponse):
    """Response for order list."""

    orders: list[OrderSummary]


class TransactionCreateResponse(BaseResponse):
    """Response after transaction creation."""

    transaction: TransactionResponse


class TransactionListResponse(BaseResponse):
    """Response for transaction list."""

    transactions: list[TransactionResponse]


class PortfolioResponse(BaseResponse):
    """Response for portfolio information."""

    portfolio: Portfolio


class TradingStatsResponse(BaseResponse):
    """Response for trading statistics."""

    stats: TradingStats
