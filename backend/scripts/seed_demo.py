"""Jeu de données de démonstration déterministe pour la soutenance.

Peuple PostgreSQL (ou SQLite en repli) avec un parcours utilisateur complet et
cohérent : un utilisateur démo + un admin, un exchange configuré (mode sandbox),
des bots utilisateur verrouillés dans différents états, leurs décisions / ordres /
trades / positions, des données OHLCV, des backtests et un portefeuille Spot.

Idempotent : relancer avec ``--reset`` remet l'utilisateur démo à zéro puis le
repeuple (état identique à chaque exécution).

Usage (dans le conteneur backend) :
    python /app/scripts/seed_demo.py --reset

Variables d'environnement requises : ``EXCHANGE_ENC_KEY`` (chiffrement des clés),
``DATABASE_URL`` ou ``POSTGRES_*`` (sinon repli SQLite).

Optionnel : si ``BINANCE_API_KEY_TEST`` et ``BINANCE_API_SECRET_TEST`` sont fournies,
l'exchange est configuré en sandbox avec ces **vraies clés Spot Testnet** (données live
testnet) au lieu des clés factices. Ce doivent être de véritables clés créées sur
https://testnet.binance.vision (des clés mainnet sont rejetées : ``code -2015``).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BACKEND_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DATABASE_ECHO", "False")

DEMO_EMAIL = "demo@cryptobot.dev"
DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Demo12345!"  # noqa: S105 - mot de passe de démonstration

ADMIN_EMAIL = "admin@cryptobot.dev"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "Admin12345!"  # noqa: S105 - mot de passe de démonstration

DEMO_SYMBOLS = ("BTCUSDC", "ETHUSDC")
BASE_PRICE = {"BTCUSDC": Decimal("60000"), "ETHUSDC": Decimal("3000")}
RNG = random.Random(20260728)  # noqa: S311 - RNG seedé pour une démo déterministe, usage non cryptographique

# Templates publiés créés par le seed : le catalogue intégré est `disabled` et les
# templates ML dépendent de la disponibilité du ml-api. Pour une démo autonome et
# déterministe, le seed fournit ses propres templates "published".
DEMO_TEMPLATES: list[dict] = [
    {
        "slug": "demo-rsi-btcusdc-1h-v1",
        "name": "Démo RSI Mean Reversion BTCUSDC 1h",
        "description": "Bot de démonstration — mean reversion RSI sur BTCUSDC 1h.",
        "model_type": "regime_classifier_v1",
        "strategy_type": "rsi_reversal",
        "symbol": "BTCUSDC",
        "timeframe": "1h",
        "signal_source": "regime_classifier_v1+rsi_reversal",
    },
    {
        "slug": "demo-trend-ethusdc-4h-v1",
        "name": "Démo Trend Following ETHUSDC 4h",
        "description": "Bot de démonstration — suivi de tendance sur ETHUSDC 4h.",
        "model_type": "trend_classifier_v1",
        "strategy_type": "moving_average_crossover",
        "symbol": "ETHUSDC",
        "timeframe": "4h",
        "signal_source": "trend_classifier_v1+moving_average_crossover",
    },
    {
        "slug": "demo-multi-btcusdc-1h-v1",
        "name": "Démo Multi-indicateurs BTCUSDC 1h",
        "description": "Bot de démonstration — combinaison d'indicateurs sur BTCUSDC 1h.",
        "model_type": "multi_indicator_v1",
        "strategy_type": "multi_indicator",
        "symbol": "BTCUSDC",
        "timeframe": "1h",
        "signal_source": "deterministic+multi_indicator",
    },
]
_DEMO_RISK_LIMITS = {
    "risk_per_trade_pct": 1.0,
    "stop_loss_pct": 2.0,
    "take_profit_pct": 4.0,
    "max_order_quote_quantity": "250",
    "max_open_orders": 1,
    "max_user_open_positions": 3,
    "max_daily_loss_pct": 5.0,
}
_DEMO_ORDER_POLICY = {
    "order_type": "MARKET",
    "quote_order_quantity": "250",
    "quote_asset": "USDC",
    "cooldown_seconds": 3600,
}


def _template_row(spec: dict) -> dict:
    return {
        **spec,
        "exchange": "binance",
        "environment": "testnet",
        "execution_params": {"demo": True},
        "risk_limits": dict(_DEMO_RISK_LIMITS),
        "order_policy": dict(_DEMO_ORDER_POLICY),
        "version": "1.0",
        "status": "published",
    }


def _utc_now_naive() -> datetime:
    """Horodatage naïf UTC, cohérent avec les colonnes TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(UTC).replace(tzinfo=None)


def _import_models() -> None:
    """Importe tous les modèles pour que Base.metadata soit peuplé avant create_all().

    ``DatabaseManager.create_tables()`` ne fait aucun import de modèle : si les
    modules ne sont pas chargés, ``create_all`` ne crée aucune table.
    """
    import auth.models  # noqa: F401  (importe bots/strategy/trading via ses propres imports)
    import market.models  # noqa: F401


def _log(message: str) -> None:
    print(f"[seed-demo] {message}")


# ---------------------------------------------------------------------------
# Nettoyage
# ---------------------------------------------------------------------------
def _reset(emails: list[str], symbols: tuple[str, ...]) -> None:
    from auth.models import User
    from market.models import MarketData
    from shared.database.connection import get_db_session

    with get_db_session() as session:
        users = session.query(User).filter(User.email.in_(emails)).all()
        for user in users:
            session.delete(user)
        deleted_market = (
            session.query(MarketData).filter(MarketData.symbol.in_(list(symbols))).delete(synchronize_session=False)
        )
    _log(f"reset: {len(users)} utilisateur(s) + {deleted_market} bougie(s) supprimés")


# ---------------------------------------------------------------------------
# Utilisateurs & paramètres
# ---------------------------------------------------------------------------
def _ensure_user(email: str, username: str, password: str, *, is_admin: bool, first: str, last: str) -> str:
    from auth.models import User
    from auth.schemas import UserCreate
    from auth.user_service import UserService
    from shared.database.connection import get_db_session

    with get_db_session() as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing is not None:
            user_id = existing.id
            existing.is_admin = is_admin
            existing.is_active = True
            _log(f"utilisateur {email} déjà présent (id={user_id})")
            return user_id

    created = UserService().create_user(
        UserCreate(email=email, username=username, password=password, first_name=first, last_name=last)
    )
    user_id = created.id
    with get_db_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if user is not None:
            user.is_admin = is_admin
    _log(f"utilisateur {email} créé (id={user_id}, admin={is_admin})")
    return user_id


def _configure_exchange(user_id: str) -> None:
    from auth.models import UserSettings
    from shared.database.connection import get_db_session

    if not os.getenv("EXCHANGE_ENC_KEY"):
        _log(
            "EXCHANGE_ENC_KEY absente : exchange NON configuré (les pages dashboard/portfolio/performance resteront bloquées)"
        )
        return

    with get_db_session() as session:
        settings = session.query(UserSettings).filter(UserSettings.user_id == user_id).first()
        if settings is None:
            _log("settings introuvables : exchange NON configuré")
            return
        # Cles testnet reelles si fournies (BINANCE_API_KEY_TEST/SECRET), sinon
        # cles factices deterministes (demo 100% hors-ligne). Mode sandbox dans les
        # deux cas -> le client ccxt tape le testnet Binance.
        use_live = bool(os.getenv("BINANCE_API_KEY_TEST") and os.getenv("BINANCE_API_SECRET_TEST"))
        api_key = os.getenv("BINANCE_API_KEY_TEST") or "demo-api-key"
        api_secret = os.getenv("BINANCE_API_SECRET_TEST") or "demo-api-secret"
        settings.set_api_credentials("binance", api_key, api_secret, mode="sandbox")
    if use_live:
        _log("exchange binance configuré (mode sandbox -- cles TESTNET reelles)")
    else:
        _log("exchange binance configuré (mode sandbox -- cles factices, hors-ligne)")


# ---------------------------------------------------------------------------
# Bots utilisateur + journal
# ---------------------------------------------------------------------------
_BOT_STATES = [
    {"status": "ACTIVE", "auto_trade": True, "trades": 14},
    {"status": "PAUSED", "auto_trade": False, "trades": 9},
    {"status": "STOPPED", "auto_trade": False, "trades": 6},
]


def _seed_bots(user_id: str) -> list[str]:
    from bots.models import (
        BotOrder,
        BotPosition,
        BotRun,
        BotTemplate,
        BotTrade,
        TradingDecision,
        UserBotInstance,
    )
    from bots.schemas import UserBotCreate
    from bots.service import bot_service
    from shared.database.connection import get_db_session

    now = _utc_now_naive()
    instance_ids: list[str] = []
    slugs = [spec["slug"] for spec in DEMO_TEMPLATES]

    with get_db_session() as session:
        for spec in DEMO_TEMPLATES:
            row = _template_row(spec)
            template = session.query(BotTemplate).filter_by(slug=row["slug"]).first()
            if template is None:
                session.add(BotTemplate(**row))
            else:
                for key, value in row.items():
                    setattr(template, key, value)
        session.flush()
        templates = session.query(BotTemplate).filter(BotTemplate.slug.in_(slugs)).order_by(BotTemplate.slug).all()
        # Valeurs détachées (évite DetachedInstanceError une fois la session fermée).
        template_rows = [(t.id, t.slug, t.symbol, t.timeframe) for t in templates]

    if not template_rows:
        _log("aucun template publié : bots non créés")
        return instance_ids

    for (template_id, template_slug, symbol, timeframe), state in zip(template_rows, _BOT_STATES, strict=False):
        try:
            response = bot_service.create_user_bot(
                user_id,
                UserBotCreate(
                    bot_template_id=template_id,
                    quote_order_quantity=Decimal("250"),
                    max_daily_loss_pct=Decimal("5"),
                ),
            )
        except Exception as exc:
            _log(f"bot {template_slug} ignoré ({exc})")
            continue

        instance_id = response.id
        instance_ids.append(instance_id)
        price = BASE_PRICE.get(symbol, Decimal("100"))

        with get_db_session() as session:
            instance = session.query(UserBotInstance).filter(UserBotInstance.id == instance_id).first()
            instance.status = state["status"]
            instance.auto_trade_enabled = state["auto_trade"]
            instance.last_decision_at = now - timedelta(minutes=30)
            session.add(
                BotRun(
                    user_bot_instance_id=instance_id,
                    user_id=user_id,
                    started_at=now - timedelta(hours=6),
                    ended_at=now - timedelta(hours=5),
                    status="COMPLETED",
                    worker_id="seed-demo",
                )
            )
            for i in range(state["trades"]):
                ts = now - timedelta(hours=state["trades"] - i)
                side = "BUY" if i % 2 == 0 else "SELL"
                qty = Decimal("0.001") if symbol.startswith("BTC") else Decimal("0.02")
                exec_price = (price * (Decimal("100") + Decimal(RNG.randint(-40, 40)) / Decimal("1000"))).quantize(
                    Decimal("0.01")
                )
                realized = Decimal(RNG.randint(-800, 1400)) / Decimal("100")
                order = BotOrder(
                    user_id=user_id,
                    user_bot_instance_id=instance_id,
                    exchange="binance",
                    environment="testnet",
                    symbol=symbol,
                    side=side,
                    order_type="MARKET",
                    quantity=qty,
                    quote_order_quantity=(qty * exec_price).quantize(Decimal("0.01")),
                    price=exec_price,
                    status="FILLED",
                    binance_order_id=f"DEMO{instance_id[:6]}{i:03d}",
                    client_order_id=f"seed-{instance_id[:8]}-{i:03d}",
                    raw_response={"demo": True},
                )
                session.add(order)
                session.flush()
                session.add(
                    BotTrade(
                        user_id=user_id,
                        order_id=order.id,
                        user_bot_instance_id=instance_id,
                        symbol=symbol,
                        side=side,
                        quantity=qty,
                        price=exec_price,
                        fee=(qty * exec_price * Decimal("0.001")).quantize(Decimal("0.00000001")),
                        fee_asset="USDC",
                        trade_time=ts,
                        raw_response={"realized_pnl": str(realized), "demo": True},
                    )
                )
                session.add(
                    TradingDecision(
                        user_bot_instance_id=instance_id,
                        user_id=user_id,
                        timestamp=ts,
                        symbol=symbol,
                        timeframe=timeframe,
                        market_snapshot={"close": str(exec_price)},
                        model_output={"confidence": RNG.randint(55, 92)},
                        strategy_signal=side,
                        risk_decision="APPROVED",
                        final_action="OPENED" if side == "BUY" else "CLOSED",
                        reason="Décision de démonstration",
                    )
                )
            realized_total = Decimal(RNG.randint(1500, 4200)) / Decimal("100")
            session.add(
                BotPosition(
                    user_id=user_id,
                    user_bot_instance_id=instance_id,
                    symbol=symbol,
                    quantity=(Decimal("0.004") if symbol.startswith("BTC") else Decimal("0.08")),
                    average_entry_price=price,
                    unrealized_pnl=Decimal(RNG.randint(100, 900)) / Decimal("100"),
                    realized_pnl=realized_total,
                )
            )
        _log(f"bot {template_slug} seedé ({state['status']}, {state['trades']} trades)")

    return instance_ids


# ---------------------------------------------------------------------------
# Données de marché
# ---------------------------------------------------------------------------
def _seed_market_data(symbols: tuple[str, ...], days: int = 60) -> None:
    from market.models import MarketData
    from shared.database.connection import get_db_session

    end = _utc_now_naive().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    total = 0
    with get_db_session() as session:
        for symbol in symbols:
            price = BASE_PRICE.get(symbol, Decimal("100"))
            cursor = start
            while cursor <= end:
                drift = Decimal(RNG.randint(-300, 320)) / Decimal("10000")
                open_price = price
                close_price = (open_price * (Decimal("1") + drift)).quantize(Decimal("0.01"))
                high = max(open_price, close_price) * Decimal("1.004")
                low = min(open_price, close_price) * Decimal("0.996")
                session.add(
                    MarketData(
                        symbol=symbol,
                        exchange="binance",
                        interval_timeframe="1h",
                        open_time=cursor,
                        close_time=cursor + timedelta(hours=1),
                        open_price=open_price,
                        high_price=high.quantize(Decimal("0.01")),
                        low_price=low.quantize(Decimal("0.01")),
                        close_price=close_price,
                        volume=Decimal(RNG.randint(10, 500)),
                    )
                )
                total += 1
                price = close_price
                cursor += timedelta(hours=1)
    _log(f"{total} bougies 1h insérées pour {', '.join(symbols)} ({days} jours)")


# ---------------------------------------------------------------------------
# Backtests
# ---------------------------------------------------------------------------
def _seed_backtests(user_id: str, symbols: tuple[str, ...]) -> None:
    from shared.database.connection import get_db_session
    from strategy.models import BacktestResult

    now = _utc_now_naive()
    start = now - timedelta(days=60)
    specs = [
        (symbols[0], "1h", "rsi_reversal", 18.4, 12.7, 1.42, 61.0, 34),
        (symbols[1], "4h", "moving_average_crossover", 9.1, 8.2, 0.95, 54.0, 22),
        (symbols[0], "1h", "multi_indicator", -4.3, 15.1, -0.31, 44.0, 41),
    ]
    with get_db_session() as session:
        for symbol, timeframe, strategy_type, ret, dd, sharpe, win, trades in specs:
            session.add(
                BacktestResult(
                    strategy_id=None,
                    user_id=user_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start,
                    end_date=now,
                    parameters={"strategy_type": strategy_type, "source": "seed-demo"},
                    results={"total_return": ret, "equity_curve": [1000.0, 1000.0 + ret * 10]},
                    metrics={
                        "total_return": ret,
                        "max_drawdown": dd,
                        "sharpe_ratio": sharpe,
                        "win_rate": win,
                        "total_trades": trades,
                    },
                    transactions=[],
                )
            )
    _log(f"{len(specs)} backtests insérés")


# ---------------------------------------------------------------------------
# Portefeuille / trading
# ---------------------------------------------------------------------------
def _seed_trading(user_id: str) -> None:
    from shared.database.connection import get_db_session
    from strategy.models import Strategy, StrategyDeployment, TradingSession
    from trading.models import Order, OrderFill, Transaction

    now = _utc_now_naive()
    symbol = "BTCUSDC"
    price = BASE_PRICE[symbol]
    with get_db_session() as session:
        strategy = Strategy(
            user_id=user_id,
            name="Démo RSI Mean Reversion",
            description="Stratégie de démonstration (soutenance).",
            strategy_type="rsi_reversal",
            parameters={"rsi_period": 14, "overbought": 70, "oversold": 30},
            is_active=True,
        )
        session.add(strategy)
        session.flush()
        deployment = StrategyDeployment(
            strategy_id=strategy.id,
            user_id=user_id,
            exchange="binance",
            symbol=symbol,
            timeframe="1h",
            amount=Decimal("1000"),
            is_paper=True,
            status="active",
            start_time=now - timedelta(days=20),
        )
        session.add(deployment)
        session.flush()
        session.add(
            TradingSession(
                deployment_id=deployment.id,
                user_id=user_id,
                start_time=now - timedelta(days=20),
                initial_balance=Decimal("1000"),
                final_balance=Decimal("1120"),
                max_trades=100,
                total_trades=6,
                profitable_trades=4,
                total_profit_loss=Decimal("120"),
                status="ACTIVE",
            )
        )
        for i in range(6):
            ts = now - timedelta(days=6 - i)
            side = "BUY" if i % 2 == 0 else "SELL"
            qty = Decimal("0.002")
            order = Order(
                deployment_id=deployment.id,
                user_id=user_id,
                exchange="binance",
                exchange_order_id=f"SEED{i:04d}",
                client_order_id=f"seed-trade-{i:04d}",
                symbol=symbol,
                order_type="MARKET",
                side=side,
                quantity=qty,
                executed_quantity=qty,
                quote_order_quantity=(qty * price).quantize(Decimal("0.01")),
                cumulative_quote_quantity=(qty * price).quantize(Decimal("0.01")),
                price=price,
                status="FILLED",
                transact_time=ts,
            )
            session.add(order)
            session.flush()
            session.add(
                OrderFill(
                    order_id=order.id,
                    trade_id=f"SEEDFILL{i:04d}",
                    price=price,
                    quantity=qty,
                    commission=Decimal("0.01"),
                    commission_asset="USDC",
                    timestamp=ts,
                )
            )
            session.add(
                Transaction(
                    user_id=user_id,
                    order_id=order.id,
                    exchange="binance",
                    transaction_type="TRADE",
                    asset="BTC",
                    amount=qty,
                    direction="IN" if side == "BUY" else "OUT",
                    quote_asset="USDC",
                    quote_amount=(qty * price).quantize(Decimal("0.01")),
                    price=price,
                    fee_amount=Decimal("0.01"),
                    fee_asset="USDC",
                    external_id=f"SEEDTX{i:04d}",
                    status="COMPLETED",
                    timestamp=ts,
                )
            )
        session.add(
            Transaction(
                user_id=user_id,
                exchange="binance",
                transaction_type="DEPOSIT",
                asset="USDC",
                amount=Decimal("1000"),
                direction="IN",
                status="COMPLETED",
                description="Dépôt initial de démonstration",
                timestamp=now - timedelta(days=20),
            )
        )
    _log("portefeuille seedé : 1 stratégie, 1 déploiement, 6 ordres, 1 dépôt")


# ---------------------------------------------------------------------------
# Entrée
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="Seed d'un jeu de données de démonstration.")
    parser.add_argument("--reset", action="store_true", help="Supprime puis recrée les données de démo.")
    args = parser.parse_args()

    from shared.database.connection import init_database

    _import_models()
    init_database()

    if args.reset:
        _reset([DEMO_EMAIL, ADMIN_EMAIL], DEMO_SYMBOLS)

    demo_id = _ensure_user(DEMO_EMAIL, DEMO_USERNAME, DEMO_PASSWORD, is_admin=False, first="Démo", last="Utilisateur")
    _ensure_user(ADMIN_EMAIL, ADMIN_USERNAME, ADMIN_PASSWORD, is_admin=True, first="Admin", last="Root")
    _configure_exchange(demo_id)
    instance_ids = _seed_bots(demo_id)
    _seed_market_data(DEMO_SYMBOLS)
    _seed_backtests(demo_id, DEMO_SYMBOLS)
    _seed_trading(demo_id)

    _log("terminé")
    _log(f"connexion démo : {DEMO_EMAIL} / {DEMO_PASSWORD}")
    _log(f"connexion admin : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    _log(f"bots créés : {len(instance_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
