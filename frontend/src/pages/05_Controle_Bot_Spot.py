"""Page Controle Bot Spot."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_exchange_prerequisite_state
from layouts.page_shell import setup_page
from prerequisites.exchange import evaluate_exchange_prerequisite
from schemas.common import BotRuntimeStatus
from services.base import ServiceError
from services.bot_control_service import BotControlService
from utils.constants import ACTION_PAUSE, ACTION_STOP, DEFAULT_EXCHANGE, EXCHANGE_CATALOG
from utils.formatters import format_datetime
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import form_submit_button as compat_form_submit_button

DEPLOY_TIMEFRAME = "1h"


def _heartbeat_label(heartbeat_at: datetime) -> str:
    delta = datetime.now(UTC) - heartbeat_at
    if delta.total_seconds() < 90:
        return "Actif"
    if delta.total_seconds() < 300:
        return "A surveiller"
    return "Retard heartbeat"


def main() -> None:
    store, user = setup_page(title="Controle Bot Spot", icon="🤖", page_key="bot_control")
    render_page_header(
        "Controle Bot Spot",
        "Supervision et actions de pilotage: start, pause, stop (avec confirmation).",
    )

    gate = evaluate_exchange_prerequisite("bot_control", user)
    if gate.missing:
        render_exchange_prerequisite_state("bot_control", cta_key="cta_exchange_bot_control")

    service = BotControlService(store)

    try:
        with st.spinner("Chargement des bots..."):
            bots = service.list_bots()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not bots:
        show_feedback("info", "Aucun bot configure.")
        return

    if gate.missing:
        render_section_title(
            "Bots Spot disponibles",
            "Configuration de l'exchange requise avant toute supervision d'execution.",
        )
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        for bot in bots:
            st.markdown(f"- **{bot.name}**")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for bot in bots:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        head_col, actions_col = st.columns([2.1, 1.2], gap="medium")
        with head_col:
            st.markdown(f"#### {bot.name}")
            render_status_badge("Statut", bot.status.value)
            render_status_badge("Mode", "LIVE" if bot.mode_live else "PAPER")
            st.caption(
                f"Strategie: {bot.strategy} | "
                f"Heartbeat: {format_datetime(bot.heartbeat_at)} "
                f"({_heartbeat_label(bot.heartbeat_at)})"
            )
            st.caption(f"Derniere action: {bot.last_action_result}")
        with actions_col:
            btn_col1, btn_col2, btn_col3 = st.columns(3)
            with btn_col1:
                if compat_button(
                    "Start",
                    key=f"start_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled or bot.status != BotRuntimeStatus.STOPPED,
                ):
                    st.session_state[f"show_start_form_{bot.id}"] = True
            with btn_col2:
                if compat_button(
                    "Pause",
                    key=f"pause_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    result = service.apply_action(bot.id, ACTION_PAUSE)
                    show_feedback("success" if result.success else "error", result.message)
                    if result.success:
                        st.rerun()
            with btn_col3:
                if compat_button(
                    "Stop",
                    key=f"stop_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    st.session_state[f"confirm_stop_{bot.id}"] = True

        if (not gate.actions_disabled) and st.session_state.get(f"confirm_stop_{bot.id}", False):
            show_feedback("warning", f"Confirmer l'arret du bot {bot.name}.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Confirmer stop", key=f"confirm_{bot.id}", type="primary"):
                    result = service.apply_action(bot.id, ACTION_STOP)
                    show_feedback("success" if result.success else "error", result.message)
                    if result.success:
                        st.session_state[f"confirm_stop_{bot.id}"] = False
                        st.rerun()
            with c2:
                if st.button("Annuler", key=f"cancel_{bot.id}"):
                    st.session_state[f"confirm_stop_{bot.id}"] = False
                    st.rerun()

        if (not gate.actions_disabled) and st.session_state.get(f"show_start_form_{bot.id}", False):
            with st.form(f"start_form_{bot.id}"):
                exchange = st.selectbox(
                    "Exchange",
                    options=list(EXCHANGE_CATALOG.keys()),
                    format_func=lambda eid: EXCHANGE_CATALOG.get(eid, eid),
                    index=list(EXCHANGE_CATALOG.keys()).index(DEFAULT_EXCHANGE),
                    key=f"start_exchange_{bot.id}",
                )
                symbol = st.text_input("Symbole", value="BTCUSDT", key=f"start_symbol_{bot.id}")
                st.caption(f"Timeframe: {DEPLOY_TIMEFRAME} (fixe pour le MVP)")
                amount = st.number_input(
                    "Montant",
                    min_value=0.0,
                    value=100.0,
                    step=10.0,
                    key=f"start_amount_{bot.id}",
                )
                c1, c2 = st.columns(2)
                with c1:
                    confirm_start = compat_form_submit_button(
                        "Confirmer le demarrage", type="primary"
                    )
                with c2:
                    cancel_start = compat_form_submit_button("Annuler")

            if cancel_start:
                st.session_state[f"show_start_form_{bot.id}"] = False
                st.rerun()

            if confirm_start:
                result = service.deploy(
                    bot.id,
                    exchange=exchange,
                    symbol=symbol,
                    timeframe=DEPLOY_TIMEFRAME,
                    amount=str(amount),
                )
                show_feedback("success" if result.success else "error", result.message)
                if result.success:
                    st.session_state[f"show_start_form_{bot.id}"] = False
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br/>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
