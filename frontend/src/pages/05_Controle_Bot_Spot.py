"""Page Controle Bot Spot."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_binance_prerequisite_state
from layouts.page_shell import setup_page
from prerequisites.binance import evaluate_binance_prerequisite
from services.base import ServiceError
from services.bot_control_service import BotControlService
from utils.constants import ACTION_PAUSE, ACTION_START, ACTION_STOP
from utils.formatters import format_datetime
from utils.streamlit_compat import button as compat_button


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

    gate = evaluate_binance_prerequisite("bot_control", user)
    if gate.missing:
        render_binance_prerequisite_state("bot_control", cta_key="cta_binance_bot_control")

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
            "Configuration Binance requise avant toute supervision d'execution.",
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
                    disabled=gate.actions_disabled,
                ):
                    result = service.apply_action(bot.id, ACTION_START)
                    show_feedback("success" if result.success else "error", result.message)
                    st.rerun()
            with btn_col2:
                if compat_button(
                    "Pause",
                    key=f"pause_{bot.id}",
                    width="stretch",
                    disabled=gate.actions_disabled,
                ):
                    result = service.apply_action(bot.id, ACTION_PAUSE)
                    show_feedback("success" if result.success else "error", result.message)
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
                    st.session_state[f"confirm_stop_{bot.id}"] = False
                    show_feedback("success" if result.success else "error", result.message)
                    st.rerun()
            with c2:
                if st.button("Annuler", key=f"cancel_{bot.id}"):
                    st.session_state[f"confirm_stop_{bot.id}"] = False
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br/>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
