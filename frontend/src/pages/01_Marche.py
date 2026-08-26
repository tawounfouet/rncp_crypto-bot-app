"""Page Marché - prix publics, accessible connecté ou non."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from components.headers import render_page_header
from layouts.page_shell import setup_page
from services.base import ServiceError
from services.market_service import MarketService
from state.session import get_theme_mode
from theme.tokens import get_theme_tokens

TIMEFRAMES = {"Dernière heure": ("1m", 60), "Dernier jour": ("1h", 24)}
COMPARE_NONE = "__none__"


def _build_candlestick_figure(klines, tokens: dict[str, str], *, title: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=[k.open_time for k in klines],
                open=[k.open for k in klines],
                high=[k.high for k in klines],
                low=[k.low for k in klines],
                close=[k.close for k in klines],
                increasing_line_color=tokens["success"],
                decreasing_line_color=tokens["danger"],
            )
        ]
    )
    fig.update_layout(
        title={"text": title, "font": {"size": 14}, "x": 0},
        margin={"l": 0, "r": 0, "t": 36, "b": 0},
        height=300,
        xaxis_rangeslider_visible=False,
        paper_bgcolor=tokens["chart_transparent"],
        plot_bgcolor=tokens["chart_transparent"],
    )
    return fig


def _fetch_and_render_klines(
    service: MarketService,
    exchange: str,
    symbol: str,
    interval: str,
    limit: int,
    tokens: dict[str, str],
    *,
    key: str,
    title: str,
) -> None:
    try:
        klines, warnings = service.get_klines(exchange, symbol, interval, limit)
    except ServiceError as exc:
        st.error(str(exc))
        return

    for warning in warnings:
        st.caption(f":orange[{warning}]")

    if not klines:
        st.info("Aucune donnée disponible pour cette période.")
        return

    st.plotly_chart(
        _build_candlestick_figure(klines, tokens, title=title), width="stretch", key=key
    )


def _render_pair_chart(
    service: MarketService,
    exchange: str,
    symbol: str,
    labels: dict[str, str],
    tokens: dict[str, str],
) -> None:
    st.subheader(symbol)
    timeframe_label = st.radio(
        "Période",
        options=list(TIMEFRAMES.keys()),
        key=f"timeframe_{symbol}",
        horizontal=True,
    )
    interval, limit = TIMEFRAMES[timeframe_label]
    _fetch_and_render_klines(
        service,
        exchange,
        symbol,
        interval,
        limit,
        tokens,
        key=f"candlestick_{symbol}",
        title=labels[exchange],
    )


def _render_pair_comparison(
    service: MarketService,
    exchange_a: str,
    exchange_b: str,
    symbol: str,
    labels: dict[str, str],
    tokens: dict[str, str],
) -> None:
    st.subheader(symbol)
    # Periode partagee : comparer deux plateformes sur des intervalles differents n'aurait pas de sens.
    timeframe_label = st.radio(
        "Période",
        options=list(TIMEFRAMES.keys()),
        key=f"timeframe_{symbol}",
        horizontal=True,
    )
    interval, limit = TIMEFRAMES[timeframe_label]

    column_a, column_b = st.columns(2)
    with column_a:
        _fetch_and_render_klines(
            service,
            exchange_a,
            symbol,
            interval,
            limit,
            tokens,
            key=f"candlestick_{symbol}_{exchange_a}",
            title=labels[exchange_a],
        )
    with column_b:
        _fetch_and_render_klines(
            service,
            exchange_b,
            symbol,
            interval,
            limit,
            tokens,
            key=f"candlestick_{symbol}_{exchange_b}",
            title=labels[exchange_b],
        )


def main() -> None:
    setup_page(title="Marché", icon=":material/monitoring:", page_key="market")
    render_page_header(
        "Marché",
        "Prix en direct, sans connexion nécessaire. Connectez-vous pour voir votre portefeuille.",
    )

    service = MarketService()

    try:
        exchanges = service.list_exchanges()
    except ServiceError as exc:
        st.error(str(exc))
        return

    if not exchanges:
        st.warning("Aucune plateforme configurée côté backend.")
        return

    labels = {exchange.id: exchange.label for exchange in exchanges}
    selected_id = st.selectbox(
        "Plateforme",
        options=list(labels.keys()),
        format_func=lambda exchange_id: labels[exchange_id],
    )

    compare_options = [COMPARE_NONE] + [
        exchange_id for exchange_id in labels if exchange_id != selected_id
    ]
    compare_id = st.selectbox(
        "Comparer avec",
        options=compare_options,
        format_func=lambda exchange_id: "Aucune"
        if exchange_id == COMPARE_NONE
        else labels[exchange_id],
    )

    try:
        prices, price_warnings = service.get_prices(selected_id)
    except ServiceError as exc:
        st.error(str(exc))
        return

    for warning in price_warnings:
        st.caption(f":orange[{warning}]")

    if not prices:
        st.info("Aucun prix disponible pour cette plateforme actuellement.")
        return

    columns = st.columns(len(prices))
    for column, price in zip(columns, prices, strict=True):
        with column:
            st.metric(label=price.symbol, value=f"{price.price:,.2f}")

    st.divider()

    tokens = get_theme_tokens(get_theme_mode())
    symbols = [price.symbol for price in prices]

    if compare_id == COMPARE_NONE:
        for row_start in range(0, len(symbols), 2):
            row_symbols = symbols[row_start : row_start + 2]
            columns = st.columns(2)
            for column, symbol in zip(columns, row_symbols, strict=False):
                with column:
                    _render_pair_chart(service, selected_id, symbol, labels, tokens)
    else:
        for symbol in symbols:
            _render_pair_comparison(service, selected_id, compare_id, symbol, labels, tokens)


if __name__ == "__main__":
    main()
