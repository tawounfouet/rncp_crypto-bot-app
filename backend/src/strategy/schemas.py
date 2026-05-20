"""
Strategy-related Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for strategy creation, deployment, and management.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas.common import BaseResponse


class StrategyTypeEnum(str, Enum):
    """Available strategy types."""

    MOVING_AVERAGE_CROSSOVER = "moving_average_crossover"
    RSI_REVERSAL = "rsi_reversal"
    BOLLINGER_BANDS = "bollinger_bands"
    GRID_TRADING = "grid_trading"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    CUSTOM = "custom"


class AssetClassEnum(str, Enum):
    """Asset classes."""

    CRYPTO = "crypto"
    FOREX = "forex"
    STOCKS = "stocks"
    COMMODITIES = "commodities"


class DeploymentStatusEnum(str, Enum):
    """Deployment statuses."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SessionStatusEnum(str, Enum):
    """Trading session statuses."""

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


# Strategy Creation and Management
class StrategyCreate(BaseModel):
    """Schema for creating a new strategy."""

    name: str = Field(..., min_length=3, max_length=200, description="Strategy name")
    description: str | None = Field(None, max_length=1000, description="Strategy description")
    strategy_type: StrategyTypeEnum
    parameters: dict[str, Any] = Field(..., description="Strategy parameters")
    asset_class: AssetClassEnum = AssetClassEnum.CRYPTO
    is_public: bool = Field(False, description="Make strategy public")
    version: str = Field("1.0", description="Strategy version")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "My MA Crossover Strategy",
                "description": "Simple moving average crossover strategy",
                "strategy_type": "moving_average_crossover",
                "parameters": {
                    "fast_period": 10,
                    "slow_period": 20,
                    "stop_loss": 0.02,
                    "take_profit": 0.05,
                },
                "asset_class": "crypto",
                "is_public": False,
            }
        }
    )


class StrategyUpdate(BaseModel):
    """Schema for updating a strategy."""

    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=1000)
    parameters: dict[str, Any] | None = None
    is_public: bool | None = None
    is_active: bool | None = None


# Strategy Deployment
class StrategyDeploymentCreate(BaseModel):
    """Schema for deploying a strategy."""

    strategy_id: str
    exchange: str = Field(..., description="Exchange name (e.g., binance)")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Timeframe (e.g., 1h, 4h, 1d)")
    amount: Decimal = Field(..., gt=0, description="Amount to trade")
    parameters: dict[str, Any] | None = Field(None, description="Deployment-specific parameters")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_id": "strategy-123",
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "amount": "100.00",
                "parameters": {"risk_per_trade": 0.01, "max_positions": 3},
            }
        }
    )


class StrategyDeploymentUpdate(BaseModel):
    """Schema for updating a deployment."""

    status: DeploymentStatusEnum | None = None
    amount: Decimal | None = Field(None, gt=0)
    parameters: dict[str, Any] | None = None
    end_time: datetime | None = None


# Trading Session
class TradingSessionCreate(BaseModel):
    """Schema for creating a trading session."""

    deployment_id: str
    initial_balance: Decimal = Field(..., gt=0)
    max_trades: int | None = Field(None, gt=0)


class TradingSessionUpdate(BaseModel):
    """Schema for updating a trading session."""

    status: SessionStatusEnum | None = None
    final_balance: Decimal | None = None
    stop_reason: str | None = None


# Backtest
class BacktestCreate(BaseModel):
    """Schema for creating a backtest."""

    strategy_id: str
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_balance: Decimal = Field(..., gt=0, description="Initial balance")
    parameters: dict[str, Any] | None = Field(None, description="Backtest parameters")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy_id": "strategy-123",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-12-31T23:59:59Z",
                "initial_balance": "1000.00",
                "parameters": {"commission": 0.001},
            }
        }
    )


# Response Models
class StrategyBase(BaseModel):
    """Base strategy fields."""

    id: str
    user_id: str
    name: str
    description: str | None = None
    strategy_type: StrategyTypeEnum
    asset_class: AssetClassEnum
    is_public: bool
    is_active: bool
    version: str
    created_at: datetime
    updated_at: datetime


class StrategyResponse(StrategyBase):
    """Complete strategy response."""

    parameters: dict[str, Any]
    parameter_hash: str | None = None
    model_config = ConfigDict(from_attributes=True)


class StrategyPublic(BaseModel):
    """Public strategy information (limited fields)."""

    id: str
    name: str
    description: str | None = None
    strategy_type: StrategyTypeEnum
    asset_class: AssetClassEnum
    version: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StrategyDeploymentResponse(BaseModel):
    """Strategy deployment response."""

    id: str
    strategy_id: str
    user_id: str
    exchange: str
    symbol: str
    timeframe: str
    amount: Decimal
    parameters: dict[str, Any] | None = None
    status: DeploymentStatusEnum
    start_time: datetime
    end_time: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StrategyStateResponse(BaseModel):
    """Strategy state response."""

    id: str
    deployment_id: str
    position: str | None = None
    position_size: Decimal
    entry_price: Decimal | None = None
    entry_time: datetime | None = None
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_profit_loss: Decimal
    cumulative_profit_loss: Decimal
    max_drawdown: Decimal
    is_active: bool
    last_signal: str | None = None
    last_signal_time: datetime | None = None
    last_price: Decimal | None = None
    last_update: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class TradingSessionResponse(BaseModel):
    """Trading session response."""

    id: str
    deployment_id: str
    user_id: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: int | None = None
    initial_balance: Decimal
    final_balance: Decimal | None = None
    max_trades: int | None = None
    total_trades: int
    profitable_trades: int
    total_profit_loss: Decimal
    win_rate: Decimal | None = None
    status: SessionStatusEnum
    stop_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BacktestResponse(BaseModel):
    """Backtest response."""

    id: str
    strategy_id: str
    user_id: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    parameters: dict[str, Any] | None = None
    results: dict[str, Any]
    metrics: dict[str, Any]
    transactions: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# Strategy Performance
class StrategyPerformance(BaseModel):
    """Strategy performance metrics."""

    strategy_id: str
    deployment_count: int
    total_orders: int
    avg_profit_loss: Decimal
    avg_win_rate: float
    max_drawdown: Decimal
    total_runtime_hours: float
    model_config = ConfigDict(from_attributes=True)


# List Response Models
class StrategyCreateResponse(BaseResponse):
    """Response after strategy creation."""

    strategy: StrategyResponse


class StrategyListResponse(BaseResponse):
    """Response for strategy list."""

    strategies: list[StrategyResponse]


class StrategyPublicListResponse(BaseResponse):
    """Response for public strategy list."""

    strategies: list[StrategyPublic]


class DeploymentCreateResponse(BaseResponse):
    """Response after deployment creation."""

    deployment: StrategyDeploymentResponse


class DeploymentListResponse(BaseResponse):
    """Response for deployment list."""

    deployments: list[StrategyDeploymentResponse]


class TradingSessionCreateResponse(BaseResponse):
    """Response after trading session creation."""

    session: TradingSessionResponse


class BacktestCreateResponse(BaseResponse):
    """Response after backtest creation."""

    backtest: BacktestResponse


class StrategyPerformanceResponse(BaseResponse):
    """Response for strategy performance."""

    performance: StrategyPerformance
