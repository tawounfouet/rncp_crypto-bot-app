"""
Trading domain models for the Crypto Trading Bot.
Contains Order, OrderFill, and Transaction models with Binance API compatibility.
"""

from datetime import datetime
from decimal import Decimal

from shared.models.base import BaseModel, register_model
from sqlalchemy import (
    DECIMAL,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import relationship


@register_model
class Order(BaseModel):
    """
    Order model - Binance API compatible order tracking.
    """

    __tablename__ = "orders"

    # Foreign keys
    deployment_id = Column(String(36), ForeignKey("strategy_deployments.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)

    # Exchange information
    exchange = Column(String(50), nullable=False, index=True)
    exchange_order_id = Column(String(100), nullable=True, index=True)  # orderId from Binance
    client_order_id = Column(String(100), nullable=True)  # clientOrderId
    order_list_id = Column(String(100), default="-1", nullable=False)  # For OCO orders

    # Order details
    symbol = Column(String(20), nullable=False, index=True)
    order_type = Column(String(20), nullable=False)  # MARKET, LIMIT, STOP_LOSS, etc.
    side = Column(String(10), nullable=False, index=True)  # BUY, SELL
    time_in_force = Column(String(10), nullable=True)  # GTC, IOC, FOK

    # Quantities and prices
    quantity = Column(DECIMAL(20, 8), nullable=False)  # origQty
    executed_quantity = Column(DECIMAL(20, 8), default=0, nullable=False)  # executedQty
    quote_order_quantity = Column(DECIMAL(20, 8), nullable=True)  # origQuoteOrderQty
    cumulative_quote_quantity = Column(DECIMAL(20, 8), nullable=True)  # cummulativeQuoteQty
    price = Column(DECIMAL(20, 8), nullable=True)  # Price for limit orders
    stop_price = Column(DECIMAL(20, 8), nullable=True)  # For stop orders

    # Status and metadata
    status = Column(String(20), nullable=False, default="NEW", index=True)
    self_trade_prevention_mode = Column(String(20), nullable=True)

    # Timestamps from exchange
    transact_time = Column(DateTime, nullable=True)
    working_time = Column(DateTime, nullable=True)

    # Relationships
    deployment = relationship("StrategyDeployment", back_populates="orders")
    user = relationship("User", back_populates="orders")
    fills = relationship("OrderFill", back_populates="order", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="order", cascade="all, delete-orphan")

    @property
    def is_filled(self) -> bool:
        """Check if the order is completely filled."""
        return self.status == "FILLED"

    @property
    def is_partially_filled(self) -> bool:
        """Check if the order is partially filled."""
        return self.status == "PARTIALLY_FILLED"

    @property
    def is_open(self) -> bool:
        """Check if the order is open (NEW or PARTIALLY_FILLED)."""
        return self.status in ["NEW", "PARTIALLY_FILLED"]

    @property
    def is_cancelled(self) -> bool:
        """Check if the order is cancelled."""
        return self.status in ["CANCELED", "REJECTED", "EXPIRED"]

    @property
    def remaining_quantity(self) -> Decimal:
        """Get remaining quantity to be filled."""
        return self.quantity - self.executed_quantity

    @property
    def fill_percentage(self) -> float:
        """Get fill percentage."""
        if self.quantity == 0:
            return 0.0
        return float((self.executed_quantity / self.quantity) * 100)

    @property
    def average_fill_price(self) -> Decimal:
        """Calculate average fill price from fills."""
        if not self.fills or self.executed_quantity == 0:
            return Decimal(0)

        total_value = sum(fill.price * fill.quantity for fill in self.fills)
        return total_value / self.executed_quantity

    @property
    def total_commission(self) -> Decimal:
        """Calculate total commission from all fills."""
        if not self.fills:
            return Decimal(0)
        return sum(fill.commission for fill in self.fills)

    def update_from_exchange_response(self, response_data: dict):
        """Update order from exchange API response."""
        # Map common Binance response fields
        if "orderId" in response_data:
            self.exchange_order_id = str(response_data["orderId"])
        if "clientOrderId" in response_data:
            self.client_order_id = response_data["clientOrderId"]
        if "status" in response_data:
            self.status = response_data["status"]
        if "executedQty" in response_data:
            self.executed_quantity = Decimal(response_data["executedQty"])
        if "cummulativeQuoteQty" in response_data:
            self.cumulative_quote_quantity = Decimal(response_data["cummulativeQuoteQty"])
        if "transactTime" in response_data:
            self.transact_time = datetime.fromtimestamp(response_data["transactTime"] / 1000)
        if "workingTime" in response_data:
            self.working_time = datetime.fromtimestamp(response_data["workingTime"] / 1000)

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, symbol={self.symbol}, side={self.side}, status={self.status})>"


@register_model
class OrderFill(BaseModel):
    """
    Order fill model - Partial execution tracking.
    """

    __tablename__ = "order_fills"

    # Foreign key
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False, index=True)

    # Fill details
    trade_id = Column(String(100), nullable=False, index=True)  # tradeId from Binance
    price = Column(DECIMAL(20, 8), nullable=False)
    quantity = Column(DECIMAL(20, 8), nullable=False)
    commission = Column(DECIMAL(20, 8), nullable=False)
    commission_asset = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Fill metadata
    is_buyer = Column(Boolean, nullable=True)
    is_maker = Column(Boolean, nullable=True)

    # Relationships
    order = relationship("Order", back_populates="fills")

    @property
    def fill_value(self) -> Decimal:
        """Calculate the value of this fill."""
        return self.price * self.quantity

    @property
    def commission_percentage(self) -> float:
        """Calculate commission as percentage of fill value."""
        fill_value = self.fill_value
        if fill_value == 0:
            return 0.0
        return float((self.commission / fill_value) * 100)

    def __repr__(self) -> str:
        return (
            f"<OrderFill(id={self.id}, order_id={self.order_id}, "
            f"trade_id={self.trade_id}, quantity={self.quantity})>"
        )


@register_model
class Transaction(BaseModel):
    """
    Transaction model - Financial movements tracking.
    """

    __tablename__ = "transactions"

    # Foreign keys
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=True, index=True)

    # Transaction details
    exchange = Column(String(50), nullable=False, index=True)
    transaction_type = Column(String(20), nullable=False, index=True)  # TRADE, DEPOSIT, WITHDRAWAL, FEE

    # Asset information
    asset = Column(String(20), nullable=False, index=True)  # BTC, USDT, ETH, etc.
    amount = Column(DECIMAL(20, 8), nullable=False)  # Always positive
    direction = Column(String(10), nullable=False, index=True)  # IN, OUT

    # For trades
    quote_asset = Column(String(20), nullable=True)  # USDT for BTCUSDT
    quote_amount = Column(DECIMAL(20, 8), nullable=True)
    price = Column(DECIMAL(20, 8), nullable=True)

    # Fees
    fee_amount = Column(DECIMAL(20, 8), nullable=True)
    fee_asset = Column(String(20), nullable=True)

    # Metadata
    external_id = Column(String(100), nullable=True, index=True)  # External ID from exchange
    status = Column(String(20), nullable=False, default="COMPLETED", index=True)
    description = Column(Text, nullable=True)

    # Transaction timestamp (separate from created_at)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Relationships
    user = relationship("User", back_populates="transactions")
    order = relationship("Order", back_populates="transactions")

    @property
    def is_trade(self) -> bool:
        """Check if this is a trading transaction."""
        return self.transaction_type == "TRADE"

    @property
    def is_deposit(self) -> bool:
        """Check if this is a deposit transaction."""
        return self.transaction_type == "DEPOSIT"

    @property
    def is_withdrawal(self) -> bool:
        """Check if this is a withdrawal transaction."""
        return self.transaction_type == "WITHDRAWAL"

    @property
    def is_fee(self) -> bool:
        """Check if this is a fee transaction."""
        return self.transaction_type == "FEE"

    @property
    def net_amount(self) -> Decimal:
        """Get net amount considering direction."""
        return self.amount if self.direction == "IN" else -self.amount

    @property
    def total_cost(self) -> Decimal:
        """Get total cost including fees."""
        cost = self.amount
        if self.fee_amount and self.fee_asset == self.asset:
            cost += self.fee_amount
        return cost

    @property
    def effective_price(self) -> Decimal:
        """Get effective price including fees (for trades)."""
        if not self.is_trade or not self.quote_amount or self.quote_amount == 0:
            return self.price or Decimal(0)

        total_cost = self.quote_amount
        if self.fee_amount and self.fee_asset == self.quote_asset:
            total_cost += self.fee_amount

        return total_cost / self.amount

    @classmethod
    def create_from_order_fill(cls, order: Order, fill: OrderFill, user_id: str) -> "Transaction":
        """Create a transaction from an order fill."""
        # Determine asset and quote asset from symbol
        # This is a simplified version - in practice, you'd need symbol mapping
        base_asset = order.symbol[:3]  # Simplified extraction
        quote_asset = order.symbol[3:]  # Simplified extraction

        return cls(
            user_id=user_id,
            order_id=order.id,
            exchange=order.exchange,
            transaction_type="TRADE",
            asset=base_asset,
            amount=fill.quantity,
            direction="IN" if order.side == "BUY" else "OUT",
            quote_asset=quote_asset,
            quote_amount=fill.quantity * fill.price,
            price=fill.price,
            fee_amount=fill.commission,
            fee_asset=fill.commission_asset,
            external_id=fill.trade_id,
            timestamp=fill.timestamp,
            description=f"{order.side} {fill.quantity} {base_asset} at {fill.price}",
        )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id={self.id}, type={self.transaction_type}, "
            f"asset={self.asset}, amount={self.amount}, direction={self.direction})>"
        )
