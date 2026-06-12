"""Page Portefeuille Spot."""

from __future__ import annotations

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except ModuleNotFoundError:
    px = None

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.cards import KpiItem, render_kpi_cards
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_binance_prerequisite_state
from components.tables import render_dataframe
from layouts.page_shell import setup_page
from prerequisites.binance import evaluate_binance_prerequisite
from services.base import ServiceError
from services.portfolio_service import PortfolioService
from state.session import get_theme_mode
from theme.plotly import pie_color_sequence, themed_layout
from utils.formatters import format_currency, format_datetime
from utils.selectors import models_to_dataframe, top_assets_with_others
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import plotly_chart as compat_plotly_chart


def _render_status_banner(snapshot) -> None:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
    with col1:
        render_status_badge("Backend", "OK" if snapshot.system_status.backend_ok else "ERROR")
    with col2:
        render_status_badge("Binance", "OK" if snapshot.system_status.binance_ok else "WARNING")
    with col3:
        st.caption(f"Derniere synchro: {format_datetime(snapshot.system_status.last_sync)}")
    with col4:
        if compat_button("Refresh", width="stretch"):
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _to_df(items: list) -> pd.DataFrame:
    return models_to_dataframe(items)


def main() -> None:
    store, user = setup_page(title="Portefeuille Spot", icon="💼", page_key="portfolio")
    render_page_header(
        "Portefeuille Spot",
        "Vue temps reel de vos actifs Spot, ordres ouverts et derniers trades.",
    )

    gate = evaluate_binance_prerequisite("portfolio", user)
    if gate.should_block_content:
        render_binance_prerequisite_state("portfolio", cta_key="cta_binance_portfolio")
        return

    service = PortfolioService(store)
    theme_mode = get_theme_mode()
    try:
        with st.spinner("Chargement du portefeuille..."):
            snapshot = service.get_snapshot()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    _render_status_banner(snapshot)
    if not snapshot.system_status.binance_ok:
        show_feedback(
            "warning",
            "Binance n'est pas configure. Ajoutez vos cles dans Gestion de compte.",
        )

    kpis = [
        KpiItem("Valeur totale", format_currency(snapshot.total_value_usdt)),
        KpiItem("Cash USDC libre", format_currency(snapshot.free_cash_usdt)),
        KpiItem("Nombre d'actifs", str(snapshot.asset_count)),
        KpiItem("Nombre d'ordres", str(snapshot.open_order_count)),
    ]
    render_kpi_cards(kpis, columns=4)

    balances_df = _to_df(snapshot.balances)
    orders_df = _to_df(snapshot.open_orders)
    trades_df = _to_df(snapshot.recent_trades)

    col_left, col_right = st.columns([1.1, 1], gap="large")
    with col_left:
        render_section_title("Allocation (Top 10 + Others)")
        if balances_df.empty:
            show_feedback("info", "Aucune allocation a afficher.")
        elif px is None:
            show_feedback("warning", "Plotly indisponible dans cet environnement de test.")
        else:
            allocation_df = top_assets_with_others(balances_df[["asset", "value_usdt"]], top_n=10)
            fig = px.pie(
                allocation_df,
                values="value_usdt",
                names="asset",
                hole=0.45,
                color_discrete_sequence=pie_color_sequence(theme_mode),
            )
            fig.update_layout(
                **themed_layout(
                    theme_mode,
                    margin=dict(l=0, r=0, t=20, b=0),
                    legend_title_text="Actifs",
                )
            )
            compat_plotly_chart(fig, width="stretch")
    with col_right:
        render_section_title("Balances Spot")
        if balances_df.empty:
            show_feedback("info", "Portefeuille vide.")
        else:
            asset_choices = sorted(balances_df["asset"].unique().tolist())
            selected_assets = st.multiselect(
                "Filtrer actifs",
                options=asset_choices,
                default=[],
                placeholder="Tous les actifs",
            )
            sort_by = st.selectbox(
                "Trier par",
                options=["value_usdt", "free", "locked", "asset"],
                index=0,
            )
            ascending = st.toggle("Ordre croissant", value=False)
            filtered = balances_df.copy()
            if selected_assets:
                filtered = filtered[filtered["asset"].isin(selected_assets)]
            filtered = filtered.sort_values(sort_by, ascending=ascending).reset_index(drop=True)
            render_dataframe(filtered, key="table_balances", height=360)

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title("Ordres ouverts", "Annulation transmise au backend.")
    if orders_df.empty:
        show_feedback("info", "Aucun ordre ouvert.")
    else:
        render_dataframe(orders_df, key="table_open_orders", height=260)
        selected_order = st.selectbox("Selection ordre", options=orders_df["order_id"].tolist())
        if st.button("Annuler l'ordre selectionne", type="secondary"):
            ok, message = service.cancel_order(selected_order)
            show_feedback("success" if ok else "error", message)

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    render_section_title("Derniers trades")
    if trades_df.empty:
        show_feedback("info", "Aucun trade recent.")
    else:
        trades_df = trades_df.sort_values("executed_at", ascending=False).reset_index(drop=True)
        symbol_filter = st.multiselect(
            "Filtrer symboles",
            options=sorted(trades_df["symbol"].unique().tolist()),
            default=[],
            key="trade_symbols",
        )
        if symbol_filter:
            trades_df = trades_df[trades_df["symbol"].isin(symbol_filter)]
        render_dataframe(trades_df, key="table_recent_trades", height=300)


if __name__ == "__main__":
    main()
