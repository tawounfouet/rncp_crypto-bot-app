"""Models for immutable bot templates and user-owned bot instances."""

from __future__ import annotations

from shared.models.base import BaseModel, register_model
from sqlalchemy import DECIMAL, JSON, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship


@register_model
class BotTemplate(BaseModel):
    """Preconfigured bot published by the product/quant team."""

    __tablename__ = "bot_templates"

    slug = Column(String(120), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    model_type = Column(String(100), nullable=False)
    strategy_type = Column(String(100), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    signal_source = Column(String(200), nullable=False)
    exchange = Column(String(50), nullable=False, default="binance", index=True)
    environment = Column(String(20), nullable=False, default="testnet", index=True)
    execution_params = Column(JSON, nullable=False, default=dict)
    risk_limits = Column(JSON, nullable=False, default=dict)
    order_policy = Column(JSON, nullable=False, default=dict)
    version = Column(String(20), nullable=False, default="1.0")
    status = Column(String(20), nullable=False, default="published", index=True)

    instances = relationship("UserBotInstance", back_populates="template")

    @property
    def is_published(self) -> bool:
        return self.status == "published"


@register_model
class UserBotInstance(BaseModel):
    """A user's selected bot, locked to the template snapshot."""

    __tablename__ = "user_bot_instances"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bot_template_id = Column(String(36), ForeignKey("bot_templates.id"), nullable=False, index=True)
    exchange_credential_id = Column(String(36), nullable=True)
    mode = Column(String(20), nullable=False, default="TESTNET", index=True)
    status = Column(String(20), nullable=False, default="STOPPED", index=True)
    auto_trade_enabled = Column(Boolean, default=False, nullable=False)
    config_snapshot = Column(JSON, nullable=False)
    last_decision_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="bot_instances")
    template = relationship("BotTemplate", back_populates="instances")
    runs = relationship("BotRun", back_populates="instance", cascade="all, delete-orphan")
    decisions = relationship("TradingDecision", back_populates="instance", cascade="all, delete-orphan")
    bot_orders = relationship("BotOrder", back_populates="instance", cascade="all, delete-orphan")
    bot_trades = relationship("BotTrade", back_populates="instance", cascade="all, delete-orphan")
    position = relationship(
        "BotPosition",
        back_populates="instance",
        uselist=False,
        cascade="all, delete-orphan",
    )


@register_model
class BotRun(BaseModel):
    """Execution run for a user bot instance."""

    __tablename__ = "bot_runs"

    user_bot_instance_id = Column(
        String(36),
        ForeignKey("user_bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default="RUNNING", index=True)
    error_message = Column(Text, nullable=True)
    worker_id = Column(String(120), nullable=True)

    user = relationship("User", back_populates="bot_runs")
    instance = relationship("UserBotInstance", back_populates="runs")
    decisions = relationship("TradingDecision", back_populates="run", cascade="all, delete-orphan")


@register_model
class TradingDecision(BaseModel):
    """Decision journal produced by model, strategy, and risk checks."""

    __tablename__ = "trading_decisions"

    user_bot_instance_id = Column(
        String(36),
        ForeignKey("user_bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id = Column(String(36), ForeignKey("bot_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    market_snapshot = Column(JSON, nullable=True)
    model_output = Column(JSON, nullable=True)
    strategy_signal = Column(String(20), nullable=False)
    risk_decision = Column(String(50), nullable=False)
    final_action = Column(String(50), nullable=False, index=True)
    reason = Column(Text, nullable=True)

    user = relationship("User", back_populates="bot_decisions")
    instance = relationship("UserBotInstance", back_populates="decisions")
    run = relationship("BotRun", back_populates="decisions")


@register_model
class BotOrder(BaseModel):
    """Order sent by a user bot to Binance Testnet."""

    __tablename__ = "bot_orders"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_bot_instance_id = Column(
        String(36),
        ForeignKey("user_bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exchange = Column(String(50), nullable=False, index=True)
    environment = Column(String(20), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False, index=True)
    order_type = Column(String(20), nullable=False)
    quantity = Column(DECIMAL(20, 8), nullable=True)
    quote_order_quantity = Column(DECIMAL(20, 8), nullable=True)
    price = Column(DECIMAL(20, 8), nullable=True)
    status = Column(String(20), nullable=False, index=True)
    binance_order_id = Column(String(100), nullable=True, index=True)
    client_order_id = Column(String(100), nullable=True, index=True)
    raw_response = Column(JSON, nullable=True)

    user = relationship("User", back_populates="bot_orders")
    instance = relationship("UserBotInstance", back_populates="bot_orders")
    trades = relationship("BotTrade", back_populates="order", cascade="all, delete-orphan")


@register_model
class BotTrade(BaseModel):
    """Trade execution returned by Binance Testnet for a bot order."""

    __tablename__ = "bot_trades"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(String(36), ForeignKey("bot_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    user_bot_instance_id = Column(
        String(36),
        ForeignKey("user_bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False, index=True)
    quantity = Column(DECIMAL(20, 8), nullable=False)
    price = Column(DECIMAL(20, 8), nullable=False)
    fee = Column(DECIMAL(20, 8), nullable=True)
    fee_asset = Column(String(20), nullable=True)
    trade_time = Column(DateTime, nullable=False, index=True)
    raw_response = Column(JSON, nullable=True)

    user = relationship("User", back_populates="bot_trades")
    order = relationship("BotOrder", back_populates="trades")
    instance = relationship("UserBotInstance", back_populates="bot_trades")


@register_model
class BotPosition(BaseModel):
    """Current exposure for one user bot instance."""

    __tablename__ = "bot_positions"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_bot_instance_id = Column(
        String(36),
        ForeignKey("user_bot_instances.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(DECIMAL(20, 8), nullable=False, default=0)
    average_entry_price = Column(DECIMAL(20, 8), nullable=True)
    unrealized_pnl = Column(DECIMAL(20, 8), nullable=False, default=0)
    realized_pnl = Column(DECIMAL(20, 8), nullable=False, default=0)

    user = relationship("User", back_populates="bot_positions")
    instance = relationship("UserBotInstance", back_populates="position")
