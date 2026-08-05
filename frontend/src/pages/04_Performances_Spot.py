"""Page Performances Spot."""

from __future__ import annotations

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
from utils.formatters import format_currency, format_pct
from utils.selectors import models_to_dataframe
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import plotly_chart as compat_plotly_chart


def main() -> None:
    store, user = setup_page(title="Performances Spot", icon="📈", page_key="performance")
    render_page_header(
        "Performances Spot",
        "Analyse detaillee des resultats de trading Spot.",
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

    filter_col1, filter_col2, filter_col3 = st.columns([1.4, 1, 0.7])
    with filter_col1:
        bot_id = st.selectbox(
            "Bot selectionne",
            options=[bot.id for bot in bots],
            format_func=lambda bid: next(bot.name for bot in bots if bot.id == bid),
        )
    with filter_col2:
        period_days = st.radio("Periode", options=[7, 30], horizontal=True, index=1)
    with filter_col3:
        st.write("")
        st.write("")
        if compat_button("Refresh", width="stretch"):
            st.rerun()

    try:
        with st.spinner("Chargement des performances..."):
            snapshot = perf_service.get_snapshot(
                bot_id=bot_id,
                period_days=period_days,
            )
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    metrics = snapshot.metrics
    render_kpi_cards(
        [
            KpiItem("PnL realise", format_currency(metrics.pnl_realized_usdt)),
            KpiItem("ROI", format_pct(metrics.roi_pct)),
            KpiItem("Max drawdown", f"{metrics.max_drawdown_pct:.2f}%"),
            KpiItem("Win rate", f"{metrics.win_rate_pct:.2f}%"),
            KpiItem("Frais", format_currency(metrics.fees_usdt)),
        ],
        columns=5,
    )
    st.caption(f"Scenario actif: {snapshot.scenario_label}")

    render_section_title("Equity curve")
    eq_df = models_to_dataframe(snapshot.equity_curve)
    if eq_df.empty:
        show_feedback("info", "Aucune donnee d'equity disponible.")
    elif go is None:
        show_feedback("warning", "Plotly indisponible dans cet environnement de test.")
    else:
        fig = go.Figure(
            data=[
                go.Scatter(
                    x=eq_df["timestamp"],
                    y=eq_df["equity_usdt"],
                    mode="lines",
                    line=dict(color=plotly_line_color(theme_mode), width=2.5),
                    name="Equity",
                )
            ]
        )
        fig.update_layout(
            **themed_layout(
                theme_mode,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="Date",
                yaxis_title="USDC",
                hovermode="x unified",
            )
        )
        fig.update_xaxes(**themed_axis(theme_mode, rangeslider=themed_rangeslider(theme_mode)))
        fig.update_yaxes(**themed_axis(theme_mode))
        compat_plotly_chart(fig, width="stretch")

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title("Journal des trades")
    trades_df = models_to_dataframe(snapshot.trade_journal)
    if trades_df.empty:
        show_feedback("info", "Aucun trade dans cette periode.")
        return
    symbol_filter = st.multiselect(
        "Filtrer symboles",
        options=sorted(trades_df["symbol"].unique().tolist()),
        default=[],
    )
    if symbol_filter:
        trades_df = trades_df[trades_df["symbol"].isin(symbol_filter)]
    trades_df = trades_df.sort_values("closed_at", ascending=False).reset_index(drop=True)
    render_dataframe(trades_df, key="performance_trade_journal", height=360)


if __name__ == "__main__":
    main()
