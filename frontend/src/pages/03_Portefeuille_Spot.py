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
from components.prerequisites import render_exchange_prerequisite_state
from components.tables import render_dataframe
from layouts.page_shell import setup_page
from prerequisites.exchange import evaluate_exchange_prerequisite
from services.account_service import AccountService
from services.base import ServiceError
from services.portfolio_service import PortfolioService
from state.session import get_selected_exchange, get_theme_mode, set_selected_exchange
from theme.plotly import pie_color_sequence, themed_layout
from utils.formatters import format_currency, format_datetime
from utils.selectors import models_to_dataframe, top_assets_with_others
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import plotly_chart as compat_plotly_chart


def _render_status_banner(snapshot) -> None:
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([1, 1, 2, 1])
        with col1:
            render_status_badge("Backend", "OK" if snapshot.system_status.backend_ok else "ERROR")
        with col2:
            render_status_badge(
                snapshot.system_status.exchange.capitalize(),
                "OK" if snapshot.system_status.exchange_ok else "WARNING",
            )
        with col3:
            st.caption(f"Derniere synchro: {format_datetime(snapshot.system_status.last_sync)}")
        with col4:
            if compat_button("Refresh", width="stretch"):
                st.rerun()


def _to_df(items: list) -> pd.DataFrame:
    return models_to_dataframe(items)


def _render_portfolio_list(store, service: PortfolioService) -> None:
    account_service = AccountService(store)
    configured = account_service.list_configured_exchanges()
    if len(configured) <= 1:
        return  # rien a comparer avec un seul exchange configure

    render_section_title("Mes portefeuilles")
    snapshots = service.list_snapshots(configured)
    current = get_selected_exchange()

    active_modes = account_service.get_active_modes(configured)
    columns = st.columns(len(configured))
    for column, exchange_id in zip(columns, configured, strict=True):
        snapshot = snapshots[exchange_id]
        mode_label = "Simulation" if active_modes.get(exchange_id) == "sandbox" else "Reel"
        with column:
            st.metric(
                label=f"{exchange_id.capitalize()} ({mode_label})",
                value=format_currency(snapshot.total_value_usdc),
            )
            if not snapshot.system_status.exchange_ok:
                st.caption(":orange[Cles invalides ou non configurees]")
            if exchange_id == current:
                st.caption("**Actif**")
            elif compat_button(
                f"Voir {exchange_id.capitalize()}", key=f"select_portfolio_{exchange_id}"
            ):
                set_selected_exchange(exchange_id)
                st.rerun()

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)


def main() -> None:
    store, user = setup_page(title="Portefeuille Spot", icon="💼", page_key="portfolio")
    render_page_header(
        "Portefeuille Spot",
        "Vue temps reel de vos actifs Spot, ordres ouverts et derniers trades.",
    )

    gate = evaluate_exchange_prerequisite("portfolio", user)
    if gate.should_block_content:
        render_exchange_prerequisite_state("portfolio", cta_key="cta_exchange_portfolio")
        return

    service = PortfolioService(store)
    _render_portfolio_list(store, service)

    theme_mode = get_theme_mode()
    try:
        with st.spinner("Chargement du portefeuille..."):
            snapshot = service.get_snapshot()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    _render_status_banner(snapshot)
    if not snapshot.system_status.exchange_ok:
        # Exchange injoignable/indisponible (ex. cles sandbox de demonstration) : on affiche
        # le message reel du backend et on CONTINUE -> les ordres/trades issus de la base
        # (seed) restent visibles au lieu d'etre masques par un return premature.
        show_feedback(
            "warning",
            f"{snapshot.system_status.exchange.capitalize()} : "
            f"{snapshot.system_status.exchange_message or 'exchange non connecte'}",
        )

    kpis = [
        KpiItem("Valeur totale", format_currency(snapshot.total_value_usdc)),
        KpiItem("Cash USDC libre", format_currency(snapshot.free_cash_usdc)),
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
            allocation_df = top_assets_with_others(balances_df[["asset", "value_usdc"]], top_n=10)
            fig = px.pie(
                allocation_df,
                values="value_usdc",
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
                options=["value_usdc", "free", "locked", "asset"],
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
