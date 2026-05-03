"""Factories de jeux de donnees mockes pour les pages."""

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random

from mocks.scenarios import MockScenario, SCENARIO_LABELS
from schemas.performance import (
    EquityPoint,
    PerformanceMetrics,
    PerformanceSnapshot,
    TradeJournalEntry,
)
from schemas.portfolio import BalanceRow, OpenOrder, PortfolioSnapshot, SpotTrade, SystemStatus


def _portfolio_balances_rich() -> list[BalanceRow]:
    rows = [
        ("BTC", 0.185, 0.010, 12940.0),
        ("ETH", 2.740, 0.150, 8900.0),
        ("SOL", 78.0, 0.0, 5760.0),
        ("BNB", 15.1, 1.2, 5210.0),
        ("XRP", 3100.0, 400.0, 2610.0),
        ("ADA", 4200.0, 0.0, 1920.0),
        ("DOGE", 18500.0, 1500.0, 1730.0),
        ("AVAX", 91.0, 7.0, 1380.0),
        ("MATIC", 2100.0, 0.0, 1160.0),
        ("LINK", 180.0, 0.0, 960.0),
        ("DOT", 140.0, 0.0, 840.0),
        ("ATOM", 100.0, 0.0, 780.0),
    ]
    return [BalanceRow(asset=a, free=f, locked=l, value_usdt=v) for a, f, l, v in rows]


def _portfolio_balances_normal() -> list[BalanceRow]:
    rows = [
        ("BTC", 0.041, 0.0, 2870.0),
        ("ETH", 0.95, 0.05, 3090.0),
        ("SOL", 26.0, 0.0, 1920.0),
        ("USDT", 2450.0, 0.0, 2450.0),
        ("LINK", 55.0, 0.0, 290.0),
    ]
    return [BalanceRow(asset=a, free=f, locked=l, value_usdt=v) for a, f, l, v in rows]


def _orders(now: datetime) -> list[OpenOrder]:
    data = [
        ("ord_101", "BTCUSDT", "BUY", 67120.0, 0.012),
        ("ord_102", "ETHUSDT", "SELL", 3320.0, 0.350),
        ("ord_103", "SOLUSDT", "BUY", 146.5, 12.0),
    ]
    items: list[OpenOrder] = []
    for idx, (oid, symbol, side, price, amount) in enumerate(data):
        items.append(
            OpenOrder(
                order_id=oid,
                symbol=symbol,
                side=side,
                price=price,
                amount=amount,
                status="OPEN",
                created_at=now - timedelta(minutes=(idx + 1) * 27),
            )
        )
    return items


def _trades(now: datetime) -> list[SpotTrade]:
    data = [
        ("trd_301", "BTCUSDT", "SELL", 67350.0, 0.01, 22.3, 0.67),
        ("trd_302", "ETHUSDT", "BUY", 3270.0, 0.45, -10.2, 0.44),
        ("trd_303", "SOLUSDT", "SELL", 149.9, 10.0, 31.8, 0.73),
        ("trd_304", "ADAUSDT", "BUY", 0.57, 900.0, -8.1, 0.51),
        ("trd_305", "BNBUSDT", "SELL", 345.0, 1.8, 11.6, 0.45),
    ]
    out: list[SpotTrade] = []
    for idx, (tid, symbol, side, price, qty, pnl, fee) in enumerate(data):
        out.append(
            SpotTrade(
                trade_id=tid,
                symbol=symbol,
                side=side,
                price=price,
                quantity=qty,
                pnl_realized=pnl,
                fee_usdt=fee,
                executed_at=now - timedelta(hours=idx + 2),
            )
        )
    return out


def build_portfolio_snapshot(
    scenario: MockScenario,
    binance_configured: bool,
    now: datetime | None = None,
) -> PortfolioSnapshot:
    current = now or datetime.utcnow()
    if scenario == MockScenario.PORTFOLIO_EMPTY:
        balances: list[BalanceRow] = []
        orders: list[OpenOrder] = []
        trades: list[SpotTrade] = []
        note = "Aucun actif pour le moment."
    elif scenario == MockScenario.PORTFOLIO_RICH:
        balances = _portfolio_balances_rich()
        orders = _orders(current)
        trades = _trades(current)
        note = "Portefeuille diversifie avec forte exposition crypto."
    else:
        balances = _portfolio_balances_normal()
        orders = _orders(current)[:2]
        trades = _trades(current)
        note = None

    total = sum(row.value_usdt for row in balances)
    free_cash = next((row.free for row in balances if row.asset == "USDT"), 0.0)
    active_binance = binance_configured and scenario != MockScenario.BINANCE_NOT_CONFIGURED

    return PortfolioSnapshot(
        system_status=SystemStatus(
            backend_ok=True,
            binance_ok=active_binance,
            last_sync=current,
            backend_message="Backend mock disponible",
            binance_message=(
                "Cles API absentes" if not active_binance else "Connexion Binance mock active"
            ),
        ),
        total_value_usdt=total,
        free_cash_usdt=free_cash,
        asset_count=len(balances),
        open_order_count=len(orders),
        balances=balances,
        open_orders=orders,
        recent_trades=trades,
        note=note,
    )


def build_performance_snapshot(
    bot_id: str,
    period_days: int,
    scenario: MockScenario,
    now: datetime | None = None,
) -> PerformanceSnapshot:
    current = now or datetime.utcnow()
    seed_map = {
        MockScenario.PERFORMANCE_STRONG: 1201,
        MockScenario.PERFORMANCE_WEAK: 902,
    }
    trend_seed = seed_map.get(scenario, 515)
    rng = Random(trend_seed + period_days)

    start_equity = 9500.0
    equity_curve: list[EquityPoint] = []
    value = start_equity

    strong = scenario == MockScenario.PERFORMANCE_STRONG
    weak = scenario == MockScenario.PERFORMANCE_WEAK

    for step in range(period_days + 1):
        day = current - timedelta(days=period_days - step)
        if strong:
            drift = rng.uniform(25.0, 90.0)
        elif weak:
            drift = rng.uniform(-110.0, 20.0)
        else:
            drift = rng.uniform(-35.0, 55.0)
        value = max(1000.0, value + drift)
        equity_curve.append(EquityPoint(timestamp=day, equity_usdt=round(value, 2)))

    pnl = equity_curve[-1].equity_usdt - equity_curve[0].equity_usdt
    roi_pct = (pnl / equity_curve[0].equity_usdt) * 100
    max_value = equity_curve[0].equity_usdt
    drawdowns: list[float] = []
    for point in equity_curve:
        max_value = max(max_value, point.equity_usdt)
        dd = ((point.equity_usdt - max_value) / max_value) * 100
        drawdowns.append(dd)
    max_drawdown = min(drawdowns)

    win_rate = 68.5 if strong else 41.3 if weak else 56.0
    fees = 126.0 if strong else 172.4 if weak else 143.8

    journal: list[TradeJournalEntry] = []
    trade_count = max(8, int(period_days * 0.8))
    for idx in range(trade_count):
        pnl_trade = (
            rng.uniform(18.0, 160.0)
            if strong
            else rng.uniform(-130.0, 70.0) if weak else rng.uniform(-70.0, 95.0)
        )
        closed_at = current - timedelta(hours=(trade_count - idx) * 6)
        entry = 100 + rng.uniform(-8.0, 8.0)
        exit_price = entry + (pnl_trade / 10.0)
        journal.append(
            TradeJournalEntry(
                id=f"pj_{idx+1:03d}",
                bot_id=bot_id,
                symbol=["BTCUSDT", "ETHUSDT", "SOLUSDT"][idx % 3],
                side="LONG" if idx % 2 == 0 else "SHORT",
                entry_price=round(entry, 2),
                exit_price=round(exit_price, 2),
                pnl_usdt=round(pnl_trade, 2),
                fee_usdt=round(rng.uniform(0.4, 3.5), 2),
                duration_min=int(rng.uniform(35, 420)),
                closed_at=closed_at,
            )
        )

    return PerformanceSnapshot(
        bot_id=bot_id,
        period_days=period_days,
        metrics=PerformanceMetrics(
            pnl_realized_usdt=round(pnl, 2),
            roi_pct=round(roi_pct, 2),
            max_drawdown_pct=round(abs(max_drawdown), 2),
            win_rate_pct=win_rate,
            fees_usdt=fees,
        ),
        equity_curve=equity_curve,
        trade_journal=journal,
        scenario_label=SCENARIO_LABELS[scenario],
    )
