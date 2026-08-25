"""
Strategy domain models for the Crypto Trading Bot.
Contains Strategy, StrategyDeployment, StrategyState, TradingSession, and BacktestResult models.
"""

from datetime import UTC, datetime
from decimal import Decimal

from shared.models.base import BaseModel, register_model
from sqlalchemy import (
    DECIMAL,
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship


@register_model
class Strategy(BaseModel):
    """
    Strategy model - Trading strategy definitions.
    """

    __tablename__ = "strategies"

    # Foreign key to user
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Strategy information
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    strategy_type = Column(String(100), nullable=False, index=True)

    # Configuration
    parameters = Column(JSON, nullable=False)
    asset_class = Column(String(50), nullable=False, default="crypto", index=True)

    # Status and visibility
    is_public = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Versioning
    version = Column(String(20), default="1.0", nullable=False)
    parameter_hash = Column(String(64), nullable=True)  # For caching and change detection

    # Relationships
    user = relationship("User", back_populates="strategies")
    deployments = relationship("StrategyDeployment", back_populates="strategy", cascade="all, delete-orphan")
    backtest_results = relationship("BacktestResult", back_populates="strategy", cascade="all, delete-orphan")

    def get_parameter(self, key: str, default=None):
        """Get a specific parameter value."""
        return self.parameters.get(key, default)

    def set_parameter(self, key: str, value):
        """Set a specific parameter value."""
        if not self.parameters:
            self.parameters = {}
        self.parameters[key] = value

    def validate_parameters(self) -> bool:
        """Validate strategy parameters (to be implemented by strategy types)."""
        # TODO: Implement parameter validation based on strategy_type
        return True

    @property
    def deployment_count(self) -> int:
        """Get the number of deployments for this strategy."""
        return len(self.deployments)

    @property
    def active_deployment_count(self) -> int:
        """Get the number of active deployments for this strategy."""
        return len([d for d in self.deployments if d.status == "active"])

    def __repr__(self) -> str:
        return f"<Strategy(id={self.id}, name={self.name}, type={self.strategy_type})>"


@register_model
class StrategyDeployment(BaseModel):
    """
    Strategy deployment model - Live trading instances.
    """

    __tablename__ = "strategy_deployments"

    # Foreign keys
    strategy_id = Column(String(36), ForeignKey("strategies.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Market configuration
    exchange = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)

    # Trading configuration
    amount = Column(DECIMAL(20, 8), nullable=False)
    parameters = Column(JSON, nullable=True)  # Deployment-specific parameters
    is_paper = Column(Boolean, nullable=False, default=True)  # True = paper trading, no real orders

    # Status and timing
    status = Column(String(20), nullable=False, default="active", index=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)

    # Relationships
    strategy = relationship("Strategy", back_populates="deployments")
    user = relationship("User", back_populates="strategy_deployments")
    state = relationship(
        "StrategyState",
        back_populates="deployment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    trading_sessions = relationship("TradingSession", back_populates="deployment", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="deployment", cascade="all, delete-orphan")

    @property
    def is_active(self) -> bool:
        """Check if the deployment is active."""
        return self.status == "active" and self.end_time is None

    @property
    def duration_seconds(self) -> int | None:
        """Get deployment duration in seconds."""
        if not self.end_time:
            return None
        return int((self.end_time - self.start_time).total_seconds())

    def stop(self, reason: str = None):
        """Stop the deployment."""
        self.status = "stopped"
        self.end_time = datetime.now(UTC)
        if self.state:
            self.state.is_active = False
            if reason:
                self.state.stop_reason = reason

    def pause(self):
        """Pause the deployment."""
        self.status = "paused"
        if self.state:
            self.state.is_active = False

    def resume(self):
        """Resume the deployment."""
        self.status = "active"
        if self.state:
            self.state.is_active = True

    def __repr__(self) -> str:
        return (
            f"<StrategyDeployment(id={self.id}, strategy_id={self.strategy_id}, "
            f"symbol={self.symbol}, status={self.status})>"
        )


@register_model
class StrategyState(BaseModel):
    """
    Strategy state model - Real-time strategy tracking.
    """

    __tablename__ = "strategy_states"

    # Foreign keys (one-to-one with deployment)
    deployment_id = Column(
        String(36),
        ForeignKey("strategy_deployments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Position information
    position = Column(String(20), nullable=True, index=True)  # LONG, SHORT, NEUTRAL
    position_size = Column(DECIMAL(20, 8), default=0, nullable=False)
    entry_price = Column(DECIMAL(20, 8), nullable=True)
    entry_time = Column(DateTime, nullable=True)

    # Trading metrics
    total_trades = Column(Integer, default=0, nullable=False)
    winning_trades = Column(Integer, default=0, nullable=False)
    losing_trades = Column(Integer, default=0, nullable=False)
    total_profit_loss = Column(DECIMAL(20, 8), default=0, nullable=False)
    cumulative_profit_loss = Column(DECIMAL(20, 8), default=0, nullable=False)
    max_drawdown = Column(DECIMAL(20, 8), default=0, nullable=False)

    # State information
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_signal = Column(String(10), nullable=True)  # BUY, SELL, HOLD
    last_signal_time = Column(DateTime, nullable=True)

    # Market data
    last_price = Column(DECIMAL(20, 8), nullable=True)
    last_update = Column(DateTime, nullable=True)

    # Relationships
    deployment = relationship("StrategyDeployment", back_populates="state")
    user = relationship("User", back_populates="strategy_states")

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def loss_rate(self) -> float:
        """Calculate loss rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.losing_trades / self.total_trades) * 100

    @property
    def average_profit_per_trade(self) -> Decimal:
        """Calculate average profit per trade."""
        if self.total_trades == 0:
            return Decimal(0)
        return self.total_profit_loss / self.total_trades

    @property
    def has_open_position(self) -> bool:
        """Check if there's an open position."""
        return self.position in ["LONG", "SHORT"] and self.position_size > 0

    def update_metrics(self, trade_profit_loss: Decimal, is_winning_trade: bool):
        """Update trading metrics after a trade."""
        self.total_trades += 1
        self.total_profit_loss += trade_profit_loss
        self.cumulative_profit_loss += trade_profit_loss

        if is_winning_trade:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Update max drawdown if necessary
        if self.cumulative_profit_loss < -self.max_drawdown:
            self.max_drawdown = -self.cumulative_profit_loss

        self.last_update = datetime.now(UTC)

    def open_position(self, position_type: str, size: Decimal, price: Decimal):
        """Open a new position."""
        self.position = position_type
        self.position_size = size
        self.entry_price = price
        self.entry_time = datetime.now(UTC)
        self.last_update = datetime.now(UTC)

    def close_position(self):
        """Close the current position."""
        self.position = "NEUTRAL"
        self.position_size = Decimal(0)
        self.entry_price = None
        self.entry_time = None
        self.last_update = datetime.now(UTC)

    def __repr__(self) -> str:
        return f"<StrategyState(id={self.id}, deployment_id={self.deployment_id}, position={self.position})>"


@register_model
class TradingSession(BaseModel):
    """
    Trading session model - Session tracking and analytics.
    """

    __tablename__ = "trading_sessions"

    # Foreign keys
    deployment_id = Column(String(36), ForeignKey("strategy_deployments.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Session timing
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Configuration
    initial_balance = Column(DECIMAL(20, 8), nullable=False)
    final_balance = Column(DECIMAL(20, 8), nullable=True)
    max_trades = Column(Integer, nullable=True)

    # Results
    total_trades = Column(Integer, default=0, nullable=False)
    profitable_trades = Column(Integer, default=0, nullable=False)
    total_profit_loss = Column(DECIMAL(20, 8), default=0, nullable=False)
    win_rate = Column(DECIMAL(5, 4), nullable=True)  # Percentage as decimal

    # Status
    status = Column(String(20), nullable=False, default="ACTIVE", index=True)
    stop_reason = Column(String(100), nullable=True)

    # Relationships
    deployment = relationship("StrategyDeployment", back_populates="trading_sessions")
    user = relationship("User", back_populates="trading_sessions")

    @property
    def is_active(self) -> bool:
        """Check if the session is active."""
        return self.status == "ACTIVE" and self.end_time is None

    @property
    def profit_loss_percentage(self) -> float:
        """Calculate profit/loss percentage."""
        if self.initial_balance == 0:
            return 0.0
        return float((self.total_profit_loss / self.initial_balance) * 100)

    @property
    def roi(self) -> float:
        """Calculate return on investment."""
        return self.profit_loss_percentage

    def end_session(self, reason: str = None):
        """End the trading session."""
        self.end_time = datetime.now(UTC)
        self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
        self.status = "COMPLETED"
        if reason:
            self.stop_reason = reason

        # Calculate final win rate
        if self.total_trades > 0:
            self.win_rate = Decimal(self.profitable_trades) / Decimal(self.total_trades)

    def __repr__(self) -> str:
        return f"<TradingSession(id={self.id}, deployment_id={self.deployment_id}, status={self.status})>"


@register_model
class BacktestResult(BaseModel):
    """
    Backtest result model - Historical strategy testing.
    """

    __tablename__ = "backtest_results"

    # Foreign keys
    strategy_id = Column(String(36), ForeignKey("strategies.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Test configuration
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)

    # Test parameters and results (JSON for flexibility)
    parameters = Column(JSON, nullable=True)  # Parameters used for the backtest
    results = Column(JSON, nullable=False)  # Complete backtest results
    metrics = Column(JSON, nullable=False)  # Performance metrics (ROI, drawdown, etc.)
    transactions = Column(JSON, nullable=True)  # List of simulated transactions

    # Relationships
    strategy = relationship("Strategy", back_populates="backtest_results")
    user = relationship("User", back_populates="backtest_results")

    def get_metric(self, metric_name: str, default=None):
        """Get a specific metric value."""
        return self.metrics.get(metric_name, default)

    def get_result(self, result_name: str, default=None):
        """Get a specific result value."""
        return self.results.get(result_name, default)

    @property
    def total_return(self) -> float:
        """Get total return percentage."""
        return self.get_metric("total_return", 0.0)

    @property
    def max_drawdown(self) -> float:
        """Get maximum drawdown percentage."""
        return self.get_metric("max_drawdown", 0.0)

    @property
    def sharpe_ratio(self) -> float:
        """Get Sharpe ratio."""
        return self.get_metric("sharpe_ratio", 0.0)

    @property
    def win_rate(self) -> float:
        """Get win rate percentage."""
        return self.get_metric("win_rate", 0.0)

    @property
    def total_trades(self) -> int:
        """Get total number of trades."""
        return self.get_metric("total_trades", 0)

    @property
    def duration_days(self) -> int:
        """Get backtest duration in days."""
        return (self.end_date - self.start_date).days

    def __repr__(self) -> str:
        return (
            f"<BacktestResult(id={self.id}, strategy_id={self.strategy_id}, "
            f"symbol={self.symbol}, total_return={self.total_return}%)>"
        )
