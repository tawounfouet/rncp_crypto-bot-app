"""
Strategy-related Pydantic schemas for the Crypto Trading Bot application.
Contains schemas for strategy creation, deployment, and management.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from enum import Enum

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
    description: Optional[str] = Field(None, max_length=1000, description="Strategy description")
    strategy_type: StrategyTypeEnum
    parameters: Dict[str, Any] = Field(..., description="Strategy parameters")
    asset_class: AssetClassEnum = AssetClassEnum.CRYPTO
    is_public: bool = Field(False, description="Make strategy public")
    version: str = Field("1.0", description="Strategy version")

    class Config:
        json_schema_extra = {
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


class StrategyUpdate(BaseModel):
    """Schema for updating a strategy."""

    name: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    parameters: Optional[Dict[str, Any]] = None
    is_public: Optional[bool] = None
    is_active: Optional[bool] = None


# Strategy Deployment
class StrategyDeploymentCreate(BaseModel):
    """Schema for deploying a strategy."""

    strategy_id: str
    exchange: str = Field(..., description="Exchange name (e.g., binance)")
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    timeframe: str = Field(..., description="Timeframe (e.g., 1h, 4h, 1d)")
    amount: Decimal = Field(..., gt=0, description="Amount to trade")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Deployment-specific parameters")

    class Config:
        json_schema_extra = {
            "example": {
                "strategy_id": "strategy-123",
                "exchange": "binance",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "amount": "100.00",
                "parameters": {"risk_per_trade": 0.01, "max_positions": 3},
            }
        }


class StrategyDeploymentUpdate(BaseModel):
    """Schema for updating a deployment."""

    status: Optional[DeploymentStatusEnum] = None
    amount: Optional[Decimal] = Field(None, gt=0)
    parameters: Optional[Dict[str, Any]] = None
    end_time: Optional[datetime] = None


# Trading Session
class TradingSessionCreate(BaseModel):
    """Schema for creating a trading session."""

    deployment_id: str
    initial_balance: Decimal = Field(..., gt=0)
    max_trades: Optional[int] = Field(None, gt=0)


class TradingSessionUpdate(BaseModel):
    """Schema for updating a trading session."""

    status: Optional[SessionStatusEnum] = None
    final_balance: Optional[Decimal] = None
    stop_reason: Optional[str] = None


# Backtest
class BacktestCreate(BaseModel):
    """Schema for creating a backtest."""

    strategy_id: str
    symbol: str = Field(..., description="Trading symbol")
    timeframe: str = Field(..., description="Timeframe")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_balance: Decimal = Field(..., gt=0, description="Initial balance")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Backtest parameters")

    class Config:
        json_schema_extra = {
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


# Response Models
class StrategyBase(BaseModel):
    """Base strategy fields."""

    id: str
    user_id: str
    name: str
    description: Optional[str]
    strategy_type: StrategyTypeEnum
    asset_class: AssetClassEnum
    is_public: bool
    is_active: bool
    version: str
    created_at: datetime
    updated_at: datetime


class StrategyResponse(StrategyBase):
    """Complete strategy response."""

    parameters: Dict[str, Any]
    parameter_hash: Optional[str]

    class Config:
        from_attributes = True


class StrategyPublic(BaseModel):
    """Public strategy information (limited fields)."""

    id: str
    name: str
    description: Optional[str]
    strategy_type: StrategyTypeEnum
    asset_class: AssetClassEnum
    version: str
    created_at: datetime

    class Config:
        from_attributes = True


class StrategyDeploymentResponse(BaseModel):
    """Strategy deployment response."""

    id: str
    strategy_id: str
    user_id: str
    exchange: str
    symbol: str
    timeframe: str
    amount: Decimal
    parameters: Optional[Dict[str, Any]]
    status: DeploymentStatusEnum
    start_time: datetime
    end_time: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StrategyStateResponse(BaseModel):
    """Strategy state response."""

    id: str
    deployment_id: str
    position: Optional[str]
    position_size: Decimal
    entry_price: Optional[Decimal]
    entry_time: Optional[datetime]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_profit_loss: Decimal
    cumulative_profit_loss: Decimal
    max_drawdown: Decimal
    is_active: bool
    last_signal: Optional[str]
    last_signal_time: Optional[datetime]
    last_price: Optional[Decimal]
    last_update: Optional[datetime]

    class Config:
        from_attributes = True


class TradingSessionResponse(BaseModel):
    """Trading session response."""

    id: str
    deployment_id: str
    user_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: Optional[int]
    initial_balance: Decimal
    final_balance: Optional[Decimal]
    max_trades: Optional[int]
    total_trades: int
    profitable_trades: int
    total_profit_loss: Decimal
    win_rate: Optional[Decimal]
    status: SessionStatusEnum
    stop_reason: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BacktestResponse(BaseModel):
    """Backtest response."""

    id: str
    strategy_id: str
    user_id: str
    symbol: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    parameters: Optional[Dict[str, Any]]
    results: Dict[str, Any]
    metrics: Dict[str, Any]
    transactions: Optional[List[Dict[str, Any]]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# List Response Models
class StrategyCreateResponse(BaseResponse):
    """Response after strategy creation."""

    strategy: StrategyResponse


class StrategyListResponse(BaseResponse):
    """Response for strategy list."""

    strategies: List[StrategyResponse]


class StrategyPublicListResponse(BaseResponse):
    """Response for public strategy list."""

    strategies: List[StrategyPublic]


class DeploymentCreateResponse(BaseResponse):
    """Response after deployment creation."""

    deployment: StrategyDeploymentResponse


class DeploymentListResponse(BaseResponse):
    """Response for deployment list."""

    deployments: List[StrategyDeploymentResponse]


class TradingSessionCreateResponse(BaseResponse):
    """Response after trading session creation."""

    session: TradingSessionResponse


class BacktestCreateResponse(BaseResponse):
    """Response after backtest creation."""

    backtest: BacktestResponse


class StrategyPerformanceResponse(BaseResponse):
    """Response for strategy performance."""

    performance: StrategyPerformance
