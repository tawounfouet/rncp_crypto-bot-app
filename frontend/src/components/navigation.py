"""Navigation et sidebar globale."""

from __future__ import annotations

import streamlit as st

from mocks.db import MockStore
from mocks.scenarios import SCENARIO_LABELS, scenario_options
from navigation.rules import sidebar_entries
from schemas.auth import MockUser
from state.session import get_theme_mode, set_theme_mode
from utils.streamlit_compat import button as compat_button


def _safe_page_link(page: str, label: str) -> None:
    try:
        st.page_link(page, label=label)
    except Exception:
        st.caption(label)


def _render_theme_switch() -> None:
    current_mode = get_theme_mode()
    selected_light = st.toggle(
        "Mode clair",
        value=current_mode == "light",
        help="Applique le theme clair/sombre sur l'ensemble de l'application.",
    )
    next_mode = "light" if selected_light else "dark"
    if next_mode != current_mode:
        set_theme_mode(next_mode)
        st.rerun()


def render_public_sidebar() -> None:
    with st.sidebar:
        _render_theme_switch()
        st.markdown("---")
        st.markdown("### Navigation")
        for entry in sidebar_entries(None):
            _safe_page_link(entry.path, label=entry.label)
        st.markdown("---")
        st.caption("Auth reelle active, pages metier encore mockees.")


def render_private_sidebar(store: MockStore, user: MockUser) -> bool:
    logout_clicked = False
    with st.sidebar:
        _render_theme_switch()
        st.markdown("---")
        st.markdown("### Navigation")
        for entry in sidebar_entries(user):
            _safe_page_link(entry.path, label=entry.label)

        st.markdown("---")
        st.caption(f"Connecte: {user.display_name}")

        options = scenario_options()
        current_idx = options.index(store.scenario)
        selected = st.selectbox(
            "Scenario global",
            options=options,
            index=current_idx,
            format_func=lambda item: SCENARIO_LABELS[item],
            help="Permet de basculer rapidement entre jeux de donnees mockes des pages metier.",
        )
        if selected != store.scenario:
            store.scenario = selected
            st.rerun()

        st.markdown("---")
        logout_clicked = compat_button("Deconnexion", type="secondary", width="stretch")
    return logout_clicked
