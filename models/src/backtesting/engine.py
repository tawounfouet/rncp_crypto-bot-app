"""Signal-to-PnL backtesting engine.

Simulates a simple long/short/neutral strategy driven by BUY/SELL/HOLD signals.
No position sizing — each signal enters at 1 unit, exits at next signal change.
Transaction costs are applied at every entry and exit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.utils.logger import get_logger


logger = get_logger(__name__)

SIGNAL_TO_POSITION = {"BUY": 1, "HOLD": 0, "SELL": -1}


@dataclass
class BacktestConfig:
    fee_rate: float = 0.001  # 0.1% Binance spot taker fee, applied on entry + exit
    slippage_rate: float = 0.0001  # 0.01% slippage estimate
    initial_capital: float = 1.0  # normalised — results are in % terms
    allow_short: bool = False  # if False, SELL signals move to HOLD
    min_hold_bars: int = 1  # minimum bars a signal must persist before acting


@dataclass
class BacktestResult:
    strategy_return: float
    buy_and_hold_return: float
    excess_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    n_trades: int
    fees_paid: float
    equity_curve: list[float] = field(default_factory=list)
    trade_returns: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_return": round(self.strategy_return, 6),
            "buy_and_hold_return": round(self.buy_and_hold_return, 6),
            "excess_return": round(self.excess_return, 6),
            "max_drawdown": round(self.max_drawdown, 6),
            "sharpe_ratio": round(self.sharpe_ratio, 6)
            if not (isinstance(self.sharpe_ratio, float) and np.isnan(self.sharpe_ratio))
            else None,
            "win_rate": round(self.win_rate, 6),
            "n_trades": self.n_trades,
            "fees_paid": round(self.fees_paid, 6),
        }


def run_backtest(
    prices: pd.Series,
    signals: list[str] | np.ndarray,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Simulate a signal-driven strategy on a price series.

    Args:
        prices: Close prices aligned with signals, sorted chronologically.
        signals: Sequence of "BUY", "SELL", or "HOLD" labels, same length as prices.
        config: BacktestConfig with fee/slippage settings.

    Returns:
        BacktestResult with PnL metrics.
    """
    if config is None:
        config = BacktestConfig()

    prices = pd.Series(prices).reset_index(drop=True)
    signals = list(signals)

    if len(prices) != len(signals):
        raise ValueError(f"prices ({len(prices)}) and signals ({len(signals)}) must have the same length")
    if len(prices) < 2:
        raise ValueError("Need at least 2 data points to backtest")

    cost_per_trade = config.fee_rate + config.slippage_rate

    # Apply signal persistence filter: only act on a signal after it has held for min_hold_bars.
    if config.min_hold_bars > 1:
        filtered = []
        for i, sig in enumerate(signals):
            start = max(0, i - config.min_hold_bars + 1)
            window = signals[start : i + 1]
            filtered.append(sig if len(set(window)) == 1 else "HOLD")
        signals = filtered

    capital = config.initial_capital
    position = 0
    fees_paid = 0.0
    equity_curve = [capital]
    trade_returns = []
    n_trades = 0

    for i in range(1, len(prices)):
        signal = signals[i]
        target_position = SIGNAL_TO_POSITION.get(signal, 0)

        if not config.allow_short and target_position == -1:
            target_position = 0

        price = float(prices.iloc[i])
        prev_price = float(prices.iloc[i - 1])

        if position != 0:
            period_return = (price - prev_price) / prev_price
            capital *= 1 + position * period_return

        if target_position != position:
            # Close existing position
            if position != 0:
                exit_cost = capital * cost_per_trade
                capital -= exit_cost
                fees_paid += exit_cost
                trade_returns.append(float(capital / equity_curve[max(0, len(equity_curve) - 1)] - 1))

            # Open new position
            if target_position != 0:
                entry_cost = capital * cost_per_trade
                capital -= entry_cost
                fees_paid += entry_cost
                n_trades += 1

            position = target_position

        equity_curve.append(capital)

    if position != 0:
        close_cost = capital * cost_per_trade
        capital -= close_cost
        fees_paid += close_cost
        equity_curve[-1] = capital

    strategy_return = (capital - config.initial_capital) / config.initial_capital
    buy_and_hold_return = float((prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0])
    excess_return = strategy_return - buy_and_hold_return

    equity_array = np.array(equity_curve)
    peaks = np.maximum.accumulate(equity_array)
    drawdowns = (equity_array - peaks) / peaks
    max_drawdown = float(drawdowns.min())

    daily_returns = pd.Series(equity_curve).pct_change().dropna()
    if daily_returns.std() > 0:
        sharpe = float(daily_returns.mean() / daily_returns.std() * np.sqrt(252))
    else:
        sharpe = float("nan")

    win_rate = float(sum(r > 0 for r in trade_returns) / len(trade_returns)) if trade_returns else float("nan")

    result = BacktestResult(
        strategy_return=strategy_return,
        buy_and_hold_return=buy_and_hold_return,
        excess_return=excess_return,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe,
        win_rate=win_rate,
        n_trades=n_trades,
        fees_paid=fees_paid,
        equity_curve=equity_curve,
        trade_returns=trade_returns,
    )

    logger.info(
        "backtest complete strategy_return=%.4f buy_hold=%.4f excess=%.4f "
        "max_drawdown=%.4f sharpe=%.4f win_rate=%.4f n_trades=%d fees=%.6f",
        result.strategy_return,
        result.buy_and_hold_return,
        result.excess_return,
        result.max_drawdown,
        result.sharpe_ratio
        if not (isinstance(result.sharpe_ratio, float) and np.isnan(result.sharpe_ratio))
        else float("nan"),
        result.win_rate if not (isinstance(result.win_rate, float) and np.isnan(result.win_rate)) else float("nan"),
        result.n_trades,
        result.fees_paid,
    )
    return result
