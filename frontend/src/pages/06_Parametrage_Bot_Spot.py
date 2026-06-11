"""Page Parametrage Bot Spot."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_binance_prerequisite_state
from layouts.page_shell import setup_page
from prerequisites.binance import evaluate_binance_prerequisite
from schemas.bot import BotConfigUpdate
from services.base import ServiceError
from services.bot_config_service import BotConfigService
from services.bot_control_service import BotControlService
from utils.formatters import format_datetime
from utils.streamlit_compat import form_submit_button as compat_form_submit_button


def main() -> None:
    store, user = setup_page(title="Parametrage Bot Spot", icon="⚙️", page_key="bot_config")
    render_page_header(
        "Parametrage Bot Spot",
        "Edition versionnee des parametres de trading avec validations explicites.",
    )

    gate = evaluate_binance_prerequisite("bot_config", user)
    if gate.missing:
        render_binance_prerequisite_state("bot_config", cta_key="cta_binance_bot_config")

    bot_service = BotControlService(store)
    config_service = BotConfigService(store)

    try:
        bots = bot_service.list_bots()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return
    if not bots:
        show_feedback("warning", "Aucun bot disponible pour parametrage.")
        return

    if gate.missing:
        render_section_title(
            "Bots Spot disponibles",
            "Le paramétrage détaillé sera disponible après configuration Binance.",
        )
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        for bot in bots:
            st.markdown(f"- **{bot.name}**")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    bot_id = st.selectbox(
        "Bot selectionne",
        options=[bot.id for bot in bots],
        format_func=lambda bid: next(bot.name for bot in bots if bot.id == bid),
        disabled=gate.actions_disabled,
    )
    selected_bot = next(bot for bot in bots if bot.id == bot_id)

    try:
        config = config_service.get_config(bot_id)
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    info_col1, info_col2, info_col3 = st.columns(3)
    with info_col1:
        render_status_badge("Statut actuel", selected_bot.status.value)
    with info_col2:
        st.metric("Version config", config.version)
    with info_col3:
        st.metric("Date modif", format_datetime(config.updated_at))

    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    with st.form("bot_config_form", clear_on_submit=False):
        strategy = st.selectbox(
            "Strategie",
            options=["Mean Reversion", "Breakout", "Trend Following", "Grid Adaptive"],
            index=max(
                0,
                (
                    ["Mean Reversion", "Breakout", "Trend Following", "Grid Adaptive"].index(
                        config.strategy
                    )
                    if config.strategy
                    in {"Mean Reversion", "Breakout", "Trend Following", "Grid Adaptive"}
                    else 0
                ),
            ),
            disabled=gate.actions_disabled,
        )
        c1, c2 = st.columns(2)
        with c1:
            budget_usdt = st.number_input(
                "Budget USDT",
                min_value=0.0,
                value=float(config.budget_usdt),
                step=100.0,
                disabled=gate.actions_disabled,
            )
            max_open_positions = st.number_input(
                "Max positions ouvertes",
                min_value=1,
                value=int(config.max_open_positions),
                step=1,
                disabled=gate.actions_disabled,
            )
            risk_per_trade = st.number_input(
                "Risque / trade (%)",
                min_value=0.1,
                max_value=10.0,
                value=float(config.risk_per_trade_pct),
                step=0.1,
                disabled=gate.actions_disabled,
            )
        with c2:
            take_profit = st.number_input(
                "Take profit (%)",
                min_value=0.1,
                value=float(config.take_profit_pct),
                step=0.1,
                disabled=gate.actions_disabled,
            )
            stop_loss = st.number_input(
                "Stop loss (%)",
                min_value=0.1,
                value=float(config.stop_loss_pct),
                step=0.1,
                disabled=gate.actions_disabled,
            )
            cooldown = st.number_input(
                "Cooldown (secondes)",
                min_value=0,
                value=int(config.cooldown_seconds),
                step=10,
                disabled=gate.actions_disabled,
            )
        validate_clicked = compat_form_submit_button(
            "Valider",
            width="stretch",
            disabled=gate.actions_disabled,
        )
        save_clicked = compat_form_submit_button(
            "Sauvegarder",
            type="primary",
            width="stretch",
            disabled=gate.actions_disabled,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    update = BotConfigUpdate(
        strategy=strategy,
        budget_usdt=float(budget_usdt),
        max_open_positions=int(max_open_positions),
        risk_per_trade_pct=float(risk_per_trade),
        take_profit_pct=float(take_profit),
        stop_loss_pct=float(stop_loss),
        cooldown_seconds=int(cooldown),
    )

    if validate_clicked:
        errors = config_service.validate(update)
        if errors:
            show_feedback("error", " | ".join(errors))
        else:
            show_feedback("success", "Validation OK. Vous pouvez sauvegarder.")

    if save_clicked:
        ok, message, new_config = config_service.save(bot_id, update)
        show_feedback("success" if ok else "error", message)
        if ok and new_config is not None:
            st.caption(
                f"Nouvelle version: {new_config.version} - date: {format_datetime(new_config.updated_at)}"
            )
            st.rerun()


if __name__ == "__main__":
    main()
