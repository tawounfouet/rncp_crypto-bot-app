"""Page Catalogue Bots Spot."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from components.prerequisites import render_binance_prerequisite_state
from layouts.page_shell import setup_page
from prerequisites.binance import evaluate_binance_prerequisite
from schemas.bot import BotTemplate
from services.base import ServiceError
from services.bot_config_service import BotConfigService
from utils.streamlit_compat import button as compat_button


def _render_mapping(title: str, values: dict[str, object]) -> None:
    st.markdown(f"##### {title}")
    for key, value in values.items():
        st.caption(f"{key}: {value}")


def _render_template_details(template: BotTemplate, already_selected: bool) -> None:
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.markdown(f"### {template.name}")
    st.caption(template.description)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Paire", template.symbol)
    with col2:
        st.metric("Timeframe", template.timeframe)
    with col3:
        st.metric("Version", template.version)
    with col4:
        render_status_badge("Statut", "DEJA CHOISI" if already_selected else "DISPONIBLE")

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.write(f"Modele IA: `{template.model_type}`")
        st.write(f"Strategie: `{template.strategy_type}`")
        st.write(f"Signal: `{template.signal_source}`")
    with c2:
        _render_mapping("Execution verrouillee", template.execution_params)
        _render_mapping("Risque verrouille", template.risk_limits)
        _render_mapping("Ordres verrouilles", template.order_policy)

    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    store, user = setup_page(
        title="Catalogue Bots Spot", icon=":material/smart_toy:", page_key="bot_config"
    )
    render_page_header(
        "Catalogue Bots Spot",
        "Selection de bots cle en main. Strategie, timeframe, signal et risque sont verrouilles.",
    )

    gate = evaluate_binance_prerequisite("bot_config", user)
    if gate.missing:
        render_binance_prerequisite_state("bot_config", cta_key="cta_binance_bot_config")

    service = BotConfigService(store)
    try:
        templates = service.list_templates()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not templates:
        show_feedback("warning", "Aucun bot preconfigure disponible.")
        return

    if gate.missing:
        render_section_title(
            "Bots Spot disponibles",
            "La selection sera disponible apres configuration Binance.",
        )
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        for template in templates:
            st.markdown(f"- **{template.name}** - `{template.symbol}` - `{template.timeframe}`")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    template_id = st.selectbox(
        "Bot preconfigure",
        options=[template.id for template in templates],
        format_func=lambda tid: next(template.name for template in templates if template.id == tid),
    )

    try:
        template = service.get_template(template_id)
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    already_selected = service.is_selected(template_id)
    _render_template_details(template, already_selected)

    if already_selected:
        show_feedback("info", "Ce bot est deja ajoute a vos instances.")
    elif compat_button("Choisir ce bot", type="primary", width="stretch"):
        ok, message, _selection = service.select_template(template_id)
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()

    selections = service.list_user_selections()
    if selections:
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
        render_section_title(
            "Mes bots selectionnes", "Instances creees depuis des templates verrouilles."
        )
        for selection in selections:
            snapshot = selection.config_snapshot
            st.markdown(
                f"- **{snapshot.get('name')}** - `{snapshot.get('symbol')}` - "
                f"`{snapshot.get('timeframe')}` - {selection.status.value}"
            )


if __name__ == "__main__":
    main()
