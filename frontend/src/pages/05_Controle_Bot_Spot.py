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
from services.base import ServiceError
from services.bot_control_service import BotControlService
from utils.constants import ACTION_PAUSE, ACTION_STOP
from utils.formatters import format_datetime
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import form_submit_button as compat_form_submit_button

_SYMBOLS = [
    "BTCUSDC",
    "ETHUSDC",
    "BNBUSDC",
    "SOLUSDC",
    "ADAUSDC",
    "XRPUSDC",
    "DOGEUSDC",
    "DOTUSDC",
    "LINKUSDC",
    "AVAXUSDC",
    "LTCUSDC",
    "UNIUSDC",
    "MATICUSDC",
    "ATOMUSDC",
    "SHIBUSDC",
]
_TIMEFRAMES = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
_EXCHANGES = ["binance", "kraken", "bybit", "coinbase", "okx"]

_STRATEGY_TYPES = {
    "moving_average_crossover": "Croisement Moyennes Mobiles",
    "rsi_reversal": "RSI Reversal",
    "bollinger_bands": "Bandes de Bollinger",
    "custom": "Personnalisé",
}

_STRATEGY_DESCRIPTIONS = {
    "moving_average_crossover": "Achète quand la MA rapide croise au-dessus de la MA lente, vend dans le sens inverse.",
    "rsi_reversal": "Achète en zone de survente (RSI bas), vend en zone de surachat (RSI élevé).",
    "bollinger_bands": "Trade les rebonds sur les bandes extrêmes, confirmés par le RSI.",
    "custom": "Paramètres libres — à définir selon votre logique de trading.",
}


def _heartbeat_label(heartbeat_at: datetime) -> str:
    aware = heartbeat_at if heartbeat_at.tzinfo is not None else heartbeat_at.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - aware
    if delta.total_seconds() < 90:
        return "Actif"
    if delta.total_seconds() < 300:
        return "A surveiller"
    return "Retard heartbeat"


def _render_create_bot_form(service: BotControlService) -> None:
    st.markdown("#### Nouveau bot")
    with st.form("create_bot_form", clear_on_submit=True):
        name = st.text_input("Nom du bot", placeholder="Ex: BTC RSI 14")
        description = st.text_input("Description (optionnel)", placeholder="Courte description")

        strategy_type = st.selectbox(
            "Type de stratégie",
            options=list(_STRATEGY_TYPES.keys()),
            format_func=lambda k: _STRATEGY_TYPES[k],
        )
        st.caption(_STRATEGY_DESCRIPTIONS.get(strategy_type, ""))

        st.markdown("**Paramètres de la stratégie**")
        params: dict = {}

        if strategy_type == "moving_average_crossover":
            c1, c2 = st.columns(2)
            with c1:
                params["fast_period"] = st.number_input(
                    "Période MA rapide", min_value=2, max_value=49, value=10
                )
                params["stop_loss"] = st.number_input(
                    "Stop loss (%)",
                    min_value=0.01,
                    max_value=0.10,
                    value=0.02,
                    step=0.005,
                    format="%.3f",
                )
            with c2:
                params["slow_period"] = st.number_input(
                    "Période MA lente", min_value=3, max_value=200, value=20
                )
                params["take_profit"] = st.number_input(
                    "Take profit (%)",
                    min_value=0.02,
                    max_value=0.20,
                    value=0.05,
                    step=0.005,
                    format="%.3f",
                )

        elif strategy_type == "rsi_reversal":
            c1, c2 = st.columns(2)
            with c1:
                params["rsi_period"] = st.number_input(
                    "Période RSI", min_value=5, max_value=30, value=14
                )
                params["oversold_threshold"] = st.number_input(
                    "Seuil survente", min_value=10, max_value=40, value=30
                )
                params["stop_loss"] = st.number_input(
                    "Stop loss (%)",
                    min_value=0.01,
                    max_value=0.10,
                    value=0.03,
                    step=0.005,
                    format="%.3f",
                )
            with c2:
                params["overbought_threshold"] = st.number_input(
                    "Seuil surachat", min_value=60, max_value=90, value=70
                )
                params["take_profit"] = st.number_input(
                    "Take profit (%)",
                    min_value=0.02,
                    max_value=0.20,
                    value=0.06,
                    step=0.005,
                    format="%.3f",
                )

        elif strategy_type == "bollinger_bands":
            c1, c2 = st.columns(2)
            with c1:
                params["bb_period"] = st.number_input(
                    "Période BB", min_value=10, max_value=50, value=20
                )
                params["bb_std"] = st.number_input(
                    "Écart-type BB", min_value=1.0, max_value=3.0, value=2.0, step=0.1
                )
                params["rsi_period"] = st.number_input(
                    "Période RSI", min_value=5, max_value=30, value=14
                )
                params["stop_loss"] = st.number_input(
                    "Stop loss (%)",
                    min_value=0.01,
                    max_value=0.10,
                    value=0.025,
                    step=0.005,
                    format="%.3f",
                )
            with c2:
                params["rsi_oversold"] = st.number_input(
                    "RSI survente", min_value=10, max_value=40, value=30
                )
                params["rsi_overbought"] = st.number_input(
                    "RSI surachat", min_value=60, max_value=90, value=70
                )
                params["take_profit"] = st.number_input(
                    "Take profit (%)",
                    min_value=0.02,
                    max_value=0.20,
                    value=0.05,
                    step=0.005,
                    format="%.3f",
                )

        else:
            c1, c2 = st.columns(2)
            with c1:
                params["stop_loss"] = st.number_input(
                    "Stop loss (%)",
                    min_value=0.01,
                    max_value=0.10,
                    value=0.02,
                    step=0.005,
                    format="%.3f",
                )
            with c2:
                params["take_profit"] = st.number_input(
                    "Take profit (%)",
                    min_value=0.02,
                    max_value=0.20,
                    value=0.05,
                    step=0.005,
                    format="%.3f",
                )

        submitted = compat_form_submit_button("Créer le bot", type="primary", width="stretch")

    if submitted:
        if not name.strip():
            show_feedback("error", "Le nom du bot est requis.")
        elif strategy_type == "moving_average_crossover" and params.get(
            "fast_period", 0
        ) >= params.get("slow_period", 0):
            show_feedback(
                "error", "La période MA rapide doit être inférieure à la période MA lente."
            )
        else:
            result = service.create_bot(
                name=name.strip(),
                strategy_type=strategy_type,
                parameters=params,
                description=description.strip() or None,
            )
            show_feedback("success" if result.success else "error", result.message)
            if result.success:
                st.session_state["show_create_bot"] = False
                st.rerun()


def _render_launch_form(service: BotControlService, bot_id: str, bot_name: str) -> None:
    """Formulaire inline de lancement d'un deployment."""
    with st.form(key=f"launch_form_{bot_id}", clear_on_submit=True):
        st.markdown(f"**Lancer un deployment — {bot_name}**")
        col1, col2 = st.columns(2)
        with col1:
            exchange = st.selectbox("Exchange", options=_EXCHANGES, key=f"lf_exchange_{bot_id}")
            symbol = st.selectbox("Paire", options=_SYMBOLS, key=f"lf_symbol_{bot_id}")
            timeframe = st.selectbox(
                "Timeframe", options=_TIMEFRAMES, index=4, key=f"lf_tf_{bot_id}"
            )
        with col2:
            amount = st.number_input(
                "Capital (USDC)",
                min_value=10.0,
                max_value=100_000.0,
                value=500.0,
                step=50.0,
                key=f"lf_amount_{bot_id}",
            )
            is_paper = st.toggle(
                "Mode Paper (simulation)",
                value=True,
                key=f"lf_paper_{bot_id}",
                help="Paper = simulation sans fonds reels. Desactivez pour trading live.",
            )
            if not is_paper:
                st.warning("Mode LIVE : des ordres reels seront passes sur votre exchange.")

        submitted = compat_form_submit_button("Lancer le bot", type="primary", width="stretch")

    if submitted:
        result = service.start_bot(
            bot_id=bot_id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            amount=float(amount),
            is_paper=is_paper,
        )
        show_feedback("success" if result.success else "error", result.message)
        if result.success:
            st.session_state[f"show_launch_{bot_id}"] = False
            st.rerun()


def main() -> None:
    store, user = setup_page(title="Controle Bot Spot", icon="🤖", page_key="bot_control")
    render_page_header(
        "Controle Bot Spot",
        "Supervision et pilotage des bots : lancement (paper / live), pause, arret.",
    )

    gate = evaluate_exchange_prerequisite("bot_control", user)
    if gate.missing:
        render_exchange_prerequisite_state("bot_control", cta_key="cta_exchange_bot_control")

    service = BotControlService(store)

    if not gate.missing:
        col_title, col_btn = st.columns([3, 1])
        with col_title:
            render_section_title("Bots Spot")
        with col_btn:
            if compat_button(
                "Nouveau bot" if not st.session_state.get("show_create_bot") else "Annuler",
                key="toggle_create_bot",
                width="stretch",
            ):
                st.session_state["show_create_bot"] = not st.session_state.get(
                    "show_create_bot", False
                )
                st.rerun()

        if st.session_state.get("show_create_bot"):
            with st.container(border=True):
                _render_create_bot_form(service)

    try:
        with st.spinner("Chargement des bots..."):
            bots = service.list_bots()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not bots:
        show_feedback("info", 'Aucun bot configuré. Cliquez sur "Nouveau bot" pour en créer un.')
        return

    if gate.missing:
        render_section_title(
            "Bots Spot disponibles",
            "Configuration de l'exchange requise avant toute supervision d'execution.",
        )
        with st.container(border=True):
            for bot in bots:
                st.markdown(f"- **{bot.name}**")
        return

    for bot in bots:
        with st.container(border=True):
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
                btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)
                with btn_col1:
                    if compat_button(
                        "Start",
                        key=f"start_{bot.id}",
                        width="stretch",
                        disabled=gate.actions_disabled,
                    ):
                        current = st.session_state.get(f"show_launch_{bot.id}", False)
                        st.session_state[f"show_launch_{bot.id}"] = not current
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
                with btn_col4:
                    if compat_button(
                        "Suppr.",
                        key=f"delete_{bot.id}",
                        width="stretch",
                    ):
                        st.session_state[f"confirm_delete_{bot.id}"] = True

            # Launch form (toggled by Start button)
            if (not gate.actions_disabled) and st.session_state.get(f"show_launch_{bot.id}", False):
                st.markdown("---")
                _render_launch_form(service, bot.id, bot.name)

            # Stop confirmation
            if (not gate.actions_disabled) and st.session_state.get(
                f"confirm_stop_{bot.id}", False
            ):
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

            # Delete confirmation
            if st.session_state.get(f"confirm_delete_{bot.id}", False):
                show_feedback("warning", f"Supprimer définitivement le bot **{bot.name}** ?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "Confirmer suppression", key=f"confirm_del_{bot.id}", type="primary"
                    ):
                        result = service.delete_bot(bot.id)
                        st.session_state[f"confirm_delete_{bot.id}"] = False
                        show_feedback("success" if result.success else "error", result.message)
                        st.rerun()
                with c2:
                    if st.button("Annuler", key=f"cancel_del_{bot.id}"):
                        st.session_state[f"confirm_delete_{bot.id}"] = False
                        st.rerun()


if __name__ == "__main__":
    main()
