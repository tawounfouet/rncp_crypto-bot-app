"""Temporary Binance Spot Testnet lab page."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from components.alerts import show_feedback
from components.headers import render_page_header, render_section_title
from layouts.page_shell import setup_page
from services.base import ServiceError
from services.binance_testnet_lab_service import BinanceTestnetLabService
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import dataframe as compat_dataframe
from utils.streamlit_compat import form_submit_button as compat_form_submit_button


def _symbol_input(key: str = "testnet_symbol") -> str:
    return st.text_input("Symbole", value="BTCUSDT", key=key).strip().upper() or "BTCUSDT"


def _store_response(key: str, payload: Any) -> None:
    st.session_state[key] = payload


def _render_payload(payload: Any) -> None:
    if isinstance(payload, list):
        if payload:
            compat_dataframe(pd.DataFrame(payload), width="stretch")
        else:
            st.info("Aucune donnee retournee.")
        return
    if isinstance(payload, dict):
        st.json(payload)
        return
    st.write(payload)


def _call_action(label: str, key: str, action) -> None:
    if compat_button(label, key=f"btn_{key}", width="stretch"):
        try:
            with st.spinner("Appel Binance Testnet en cours..."):
                _store_response(key, action())
            show_feedback("success", "Operation Testnet terminee.")
        except ServiceError as exc:
            show_feedback("error", str(exc))
    if key in st.session_state:
        _render_payload(st.session_state[key])


def _order_payload(prefix: str) -> dict[str, Any]:
    symbol = st.text_input("Symbole ordre", value="BTCUSDT", key=f"{prefix}_symbol").strip().upper()
    side = st.selectbox("Side", ["BUY", "SELL"], key=f"{prefix}_side")
    order_type = st.selectbox("Type", ["LIMIT", "MARKET"], key=f"{prefix}_type")
    quantity = st.text_input("Quantite base", value="0.001", key=f"{prefix}_quantity")
    quote_order_quantity = st.text_input(
        "Quantite quote (optionnelle)", value="", key=f"{prefix}_quote_qty"
    )
    price = st.text_input("Prix limite", value="", key=f"{prefix}_price")
    time_in_force = st.selectbox("Time in force", ["GTC", "IOC", "FOK"], key=f"{prefix}_tif")

    payload: dict[str, Any] = {
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity or None,
        "quote_order_quantity": quote_order_quantity or None,
        "price": price or None,
        "time_in_force": time_in_force,
    }
    if order_type == "MARKET":
        payload["price"] = None
    return payload


def _render_status_tab(service: BinanceTestnetLabService) -> None:
    render_section_title("Connexion et compte")
    symbol = _symbol_input("overview_symbol")
    col1, col2 = st.columns(2)
    with col1:
        _call_action("Tester API Testnet", "testnet_ping", service.ping)
    with col2:
        _call_action(
            "Charger synthese compte", "testnet_overview", lambda: service.overview(symbol)
        )

    render_section_title("Balances")
    _call_action(
        "Charger balances non-nulles", "testnet_balances", lambda: service.balances(non_zero=True)
    )


def _render_market_tab(service: BinanceTestnetLabService) -> None:
    render_section_title("Marche")
    symbol = _symbol_input("market_symbol")
    col1, col2, col3 = st.columns(3)
    with col1:
        _call_action("Ticker 24h", "testnet_ticker", lambda: service.ticker(symbol))
    with col2:
        _call_action("Infos symbole", "testnet_symbol_info", lambda: service.symbol_info(symbol))
    with col3:
        _call_action("Ordres ouverts", "testnet_open_orders", lambda: service.open_orders(symbol))


def _render_history_tab(service: BinanceTestnetLabService) -> None:
    render_section_title("Historique")
    symbol = _symbol_input("history_symbol")
    limit = st.number_input("Limite", min_value=1, max_value=500, value=50, step=10)
    col1, col2 = st.columns(2)
    with col1:
        _call_action("Ordres", "testnet_all_orders", lambda: service.all_orders(symbol, int(limit)))
    with col2:
        _call_action(
            "Trades executes", "testnet_my_trades", lambda: service.my_trades(symbol, int(limit))
        )


def _render_orders_tab(service: BinanceTestnetLabService) -> None:
    render_section_title("Validation ordre")
    with st.form("testnet_test_order_form", clear_on_submit=False):
        test_payload = _order_payload("test_order")
        submit_test = compat_form_submit_button("Valider sans execution", width="stretch")
    if submit_test:
        try:
            _store_response("testnet_test_order", service.test_order(test_payload))
            show_feedback("success", "Ordre valide par Binance Testnet.")
        except ServiceError as exc:
            show_feedback("error", str(exc))
    if "testnet_test_order" in st.session_state:
        _render_payload(st.session_state["testnet_test_order"])

    render_section_title("Execution ordre Testnet")
    with st.form("testnet_real_order_form", clear_on_submit=False):
        real_payload = _order_payload("real_order")
        confirmed = st.checkbox("Confirmer l'envoi d'un ordre reel sur Binance Spot Testnet")
        submit_real = compat_form_submit_button(
            "Envoyer ordre Testnet",
            type="primary",
            width="stretch",
            disabled=not confirmed,
        )
    if submit_real:
        try:
            _store_response("testnet_real_order", service.place_order(real_payload))
            show_feedback("success", "Ordre envoye sur Binance Spot Testnet.")
        except ServiceError as exc:
            show_feedback("error", str(exc))
    if "testnet_real_order" in st.session_state:
        _render_payload(st.session_state["testnet_real_order"])


def _render_cancel_tab(service: BinanceTestnetLabService) -> None:
    render_section_title("Annulation")
    with st.form("testnet_cancel_order_form", clear_on_submit=False):
        symbol = st.text_input("Symbole", value="BTCUSDT", key="cancel_symbol").strip().upper()
        order_id = st.text_input("Order ID", value="")
        orig_client_order_id = st.text_input("Client Order ID (optionnel)", value="")
        submit_cancel = compat_form_submit_button("Annuler ordre", width="stretch")
    if submit_cancel:
        payload = {
            "symbol": symbol,
            "order_id": int(order_id) if order_id.strip() else None,
            "orig_client_order_id": orig_client_order_id.strip() or None,
        }
        try:
            _store_response("testnet_cancel_order", service.cancel_order(payload))
            show_feedback("success", "Ordre annule sur Binance Spot Testnet.")
        except (ServiceError, ValueError) as exc:
            show_feedback("error", str(exc))
    if "testnet_cancel_order" in st.session_state:
        _render_payload(st.session_state["testnet_cancel_order"])

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    cancel_all_symbol = st.text_input("Symbole annulation globale", value="BTCUSDT")
    confirm_all = st.checkbox("Confirmer l'annulation de tous les ordres ouverts sur ce symbole")
    if compat_button(
        "Annuler tous les ordres ouverts",
        key="cancel_all_open_orders",
        type="secondary",
        width="stretch",
        disabled=not confirm_all,
    ):
        try:
            _store_response(
                "testnet_cancel_all",
                service.cancel_open_orders(cancel_all_symbol.strip().upper()),
            )
            show_feedback("success", "Ordres ouverts annules.")
        except ServiceError as exc:
            show_feedback("error", str(exc))
    if "testnet_cancel_all" in st.session_state:
        _render_payload(st.session_state["testnet_cancel_all"])


def main() -> None:
    setup_page(
        title="Binance Testnet Lab", icon=":material/science:", page_key="binance_testnet_lab"
    )
    render_page_header(
        "Binance Testnet Lab",
        "Page temporaire isolee pour tester les cles Binance Spot Testnet.",
    )

    service = BinanceTestnetLabService()
    if not service.has_backend_session():
        show_feedback(
            "warning",
            "Session backend requise. Connectez-vous avec un compte reel pour utiliser le lab Testnet.",
        )
        return

    tabs = st.tabs(["Compte", "Marche", "Ordres", "Historique", "Annulation"])
    with tabs[0]:
        _render_status_tab(service)
    with tabs[1]:
        _render_market_tab(service)
    with tabs[2]:
        _render_orders_tab(service)
    with tabs[3]:
        _render_history_tab(service)
    with tabs[4]:
        _render_cancel_tab(service)


if __name__ == "__main__":
    main()
