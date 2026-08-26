"""Page Performances Spot."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from components.alerts import show_feedback
from components.cards import KpiItem, render_kpi_cards
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_exchange_prerequisite_state
from components.tables import render_dataframe
from layouts.page_shell import setup_page
from prerequisites.exchange import evaluate_exchange_prerequisite
from services.base import ServiceError
from services.bot_control_service import BotControlService
from services.performance_service import PerformanceService
from state.session import get_theme_mode
from theme.plotly import plotly_line_color, themed_axis, themed_layout, themed_rangeslider
from utils.formatters import format_currency, format_datetime, format_pct
from utils.selectors import models_to_dataframe
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import plotly_chart as compat_plotly_chart

MISSING_VALUE = "Donnée indisponible"


def main() -> None:
    store, user = setup_page(title="Performances Spot", icon="📈", page_key="performance")
    render_page_header(
        "Performances Spot",
        "Resultats reels issus des decisions, ordres, trades et positions des bots Spot.",
    )

    gate = evaluate_exchange_prerequisite("performance", user)
    if gate.should_block_content:
        render_exchange_prerequisite_state("performance", cta_key="cta_exchange_performance")
        return

    bot_service = BotControlService(store)
    perf_service = PerformanceService(store)
    theme_mode = get_theme_mode()

    try:
        bots = bot_service.list_bots()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return
    if not bots:
        show_feedback("warning", "Aucun bot disponible.")
        return

    bot_options: list[str | None] = [None] + [bot.id for bot in bots]

    filter_col1, filter_col2, filter_col3 = st.columns([1.7, 1, 0.7])
    with filter_col1:
        selected_bot_id = st.selectbox(
            "Bot",
            options=bot_options,
            format_func=lambda bid: "Tous les bots"
            if bid is None
            else next(bot.name for bot in bots if bot.id == bid),
        )
    with filter_col2:
        period_days = st.selectbox(
            "Periode",
            options=[7, 30, 90, 0],
            index=1,
            format_func=lambda value: "Tout l'historique" if value == 0 else f"{value} jours",
        )
    with filter_col3:
        st.write("")
        st.write("")
        if compat_button("Refresh", width="stretch"):
            st.rerun()

    try:
        with st.spinner("Chargement des performances..."):
            dashboard = perf_service.get_dashboard(
                period_days=period_days,
                bot_id=selected_bot_id,
            )
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    for reason in dashboard.unavailable_reasons:
        show_feedback("warning", f"{MISSING_VALUE} - {reason.field}: {reason.reason}")

    metrics = dashboard.global_performance
    render_kpi_cards(
        [
            KpiItem("Capital initial", _currency_or_missing(metrics.capital_initial)),
            KpiItem("Capital actuel", _currency_or_missing(metrics.capital_current)),
            KpiItem("PnL total", _currency_or_missing(metrics.pnl_total)),
            KpiItem("PnL realise", _currency_or_missing(metrics.pnl_realized)),
            KpiItem("PnL latent", _currency_or_missing(metrics.pnl_unrealized)),
            KpiItem("Ordres", str(metrics.total_orders)),
            KpiItem("Trades", str(metrics.total_trades)),
            KpiItem("Win rate", _pct_or_missing(metrics.win_rate_pct)),
        ],
        columns=4,
    )
    st.caption(
        f"Source: {dashboard.scenario_label} | Genere le {format_datetime(dashboard.generated_at)}"
    )

    render_section_title("PnL dans le temps")
    curve_df = models_to_dataframe(dashboard.pnl_curve)
    if curve_df.empty:
        show_feedback("info", f"{MISSING_VALUE} - aucun trade avec PnL realise sur cette periode.")
    elif go is None:
        show_feedback("warning", "Plotly indisponible dans cet environnement de test.")
    else:
        y_column = (
            "capital_current"
            if curve_df["capital_current"].notna().any()
            else "cumulative_realized_pnl"
        )
        chart_name = "Capital actuel" if y_column == "capital_current" else "PnL realise cumule"
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=curve_df["timestamp"],
                    y=curve_df[y_column],
                    mode="lines",
                    line=dict(color=plotly_line_color(theme_mode), width=2.5),
                    name=chart_name,
                )
            ]
        )
        fig.update_layout(
            **themed_layout(
                theme_mode,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="Date",
                yaxis_title="USDT",
                hovermode="x unified",
            )
        )
        fig.update_xaxes(**themed_axis(theme_mode, rangeslider=themed_rangeslider(theme_mode)))
        fig.update_yaxes(**themed_axis(theme_mode))
        compat_plotly_chart(fig, width="stretch")

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title(
        "Performance par bot",
        "Contribution au PnL total calculee sur la periode filtree.",
    )
    bot_df = _table_dataframe(
        dashboard.bots,
        [
            "bot_name",
            "model_name",
            "model_version",
            "pnl_total",
            "pnl_realized",
            "pnl_unrealized",
            "trades",
            "orders",
            "last_decision",
            "last_ai_signal",
            "average_confidence",
            "pnl_contribution_pct",
        ],
        {
            "pnl_total": _currency_or_missing,
            "pnl_realized": _currency_or_missing,
            "pnl_unrealized": _currency_or_missing,
            "average_confidence": _confidence_or_missing,
            "pnl_contribution_pct": lambda value: _pct_or_missing(value, signed=True),
        },
        {
            "bot_name": "Bot",
            "model_name": "Modele",
            "model_version": "Version",
            "pnl_total": "PnL bot",
            "pnl_realized": "PnL realise",
            "pnl_unrealized": "PnL latent",
            "trades": "Trades",
            "orders": "Ordres",
            "last_decision": "Derniere decision",
            "last_ai_signal": "Dernier signal IA",
            "average_confidence": "Confiance moyenne",
            "pnl_contribution_pct": "Contribution PnL",
        },
    )
    if bot_df.empty:
        show_feedback("info", "Aucun bot ne correspond aux filtres.")
    else:
        render_dataframe(bot_df, key="performance_by_bot", height=320)

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title("Historiques")
    decisions_tab, orders_tab, trades_tab = st.tabs(["Decisions", "Ordres", "Trades"])

    with decisions_tab:
        decisions_df = _table_dataframe(
            dashboard.decisions,
            [
                "timestamp",
                "bot_name",
                "model_source",
                "registry_source",
                "model_name",
                "model_version",
                "confidence",
                "raw_ai_signal",
                "deterministic_signal",
                "final_action",
                "risk_decision",
                "reason",
            ],
            {
                "timestamp": _datetime_or_missing,
                "confidence": _confidence_or_missing,
            },
            {
                "timestamp": "Date",
                "bot_name": "Bot",
                "model_source": "Source modele",
                "registry_source": "Registry",
                "model_name": "Modele",
                "model_version": "Version",
                "confidence": "Confiance",
                "raw_ai_signal": "Signal IA",
                "deterministic_signal": "Signal deterministe",
                "final_action": "Decision finale",
                "risk_decision": "Risk Manager",
                "reason": "Raison",
            },
        )
        if decisions_df.empty:
            show_feedback("info", "Aucune decision sur cette periode.")
        else:
            render_dataframe(decisions_df, key="performance_decisions", height=360)

    with orders_tab:
        orders_df = _table_dataframe(
            dashboard.orders,
            [
                "created_at",
                "bot_name",
                "symbol",
                "side",
                "order_type",
                "status",
                "binance_order_id",
                "quote_order_quantity",
                "quantity",
            ],
            {
                "created_at": _datetime_or_missing,
                "quote_order_quantity": _number_or_missing,
                "quantity": _number_or_missing,
            },
            {
                "created_at": "Date",
                "bot_name": "Bot",
                "symbol": "Symbole",
                "side": "Side",
                "order_type": "Type",
                "status": "Statut",
                "binance_order_id": "Order Binance",
                "quote_order_quantity": "Quote qty",
                "quantity": "Qty",
            },
        )
        if orders_df.empty:
            show_feedback("info", "Aucun ordre sur cette periode.")
        else:
            render_dataframe(orders_df, key="performance_orders", height=360)

    with trades_tab:
        trades_df = _table_dataframe(
            dashboard.trades,
            [
                "trade_time",
                "bot_name",
                "symbol",
                "side",
                "quantity",
                "price",
                "fee",
                "fee_asset",
                "realized_pnl",
            ],
            {
                "trade_time": _datetime_or_missing,
                "quantity": _number_or_missing,
                "price": _number_or_missing,
                "fee": _number_or_missing,
                "realized_pnl": _currency_or_missing,
            },
            {
                "trade_time": "Date",
                "bot_name": "Bot",
                "symbol": "Symbole",
                "side": "Side",
                "quantity": "Qty",
                "price": "Prix",
                "fee": "Frais",
                "fee_asset": "Asset frais",
                "realized_pnl": "PnL realise",
            },
        )
        if trades_df.empty:
            show_feedback("info", "Aucun trade sur cette periode.")
        else:
            render_dataframe(trades_df, key="performance_trades", height=360)


def _table_dataframe(
    items: list[object],
    columns: list[str],
    formatters: dict[str, Callable[[object], str]],
    labels: dict[str, str],
) -> pd.DataFrame:
    df = models_to_dataframe(items)
    if df.empty:
        return df
    selected_columns = [column for column in columns if column in df.columns]
    if not selected_columns:
        return pd.DataFrame()
    table = df[selected_columns].copy()
    for column, formatter in formatters.items():
        if column in table.columns:
            table[column] = table[column].map(formatter)
    table = table.rename(columns=labels)
    return table.fillna(MISSING_VALUE)


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except TypeError:
        return False


def _currency_or_missing(value: object) -> str:
    if _is_missing(value):
        return MISSING_VALUE
    return format_currency(float(value))


def _number_or_missing(value: object) -> str:
    if _is_missing(value):
        return MISSING_VALUE
    return f"{float(value):,.8f}".replace(",", " ")


def _pct_or_missing(value: object, *, signed: bool = False) -> str:
    if _is_missing(value):
        return MISSING_VALUE
    number = float(value)
    return format_pct(number) if signed else f"{number:.2f}%"


def _confidence_or_missing(value: object) -> str:
    if _is_missing(value):
        return MISSING_VALUE
    number = float(value)
    if 0 <= number <= 1:
        return f"{number:.1%}"
    return f"{number:.3f}"


def _datetime_or_missing(value: object) -> str:
    if _is_missing(value):
        return MISSING_VALUE
    if isinstance(value, datetime):
        return format_datetime(value)
    return str(value)


if __name__ == "__main__":
    main()
