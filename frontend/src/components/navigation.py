"""Navigation et sidebar globale."""

from __future__ import annotations

import base64
import functools
import os
from pathlib import Path

import streamlit as st

from mocks.db import MockStore
from mocks.scenarios import SCENARIO_LABELS, scenario_options
from navigation.rules import sidebar_entries
from schemas.auth import MockUser
from state.session import get_theme_mode, set_theme_mode
from utils.streamlit_compat import button as compat_button

ENV_COLORS = {
    "development": "blue",
    "staging": "orange",
    "production": "green",
}

LOGO_PATH = Path(__file__).resolve().parent.parent.parent / "assets" / "crypto_bot_logo.png"


def _safe_page_link(page: str, label: str) -> None:
    try:
        st.page_link(page, label=label)
    except Exception:
        st.caption(label)


@functools.lru_cache(maxsize=1)
def _logo_data_uri() -> str | None:
    """Encode le logo en base64 une fois : evite de relire/re-encoder le fichier a chaque rerun."""
    if not LOGO_PATH.exists():
        return None
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _render_brand_badge() -> None:
    data_uri = _logo_data_uri()
    if data_uri:
        # <img> HTML brut : st.image() ignorait la largeur demandee. Taille/centrage
        # geres via id + conteneur text-align:center dans theme/styles.py (aucun
        # attribut inline ici, cf. test_theme_hardcoded_audit.py).
        st.markdown(
            f"<div class='sidebar-logo-wrap'>"
            f"<img src='{data_uri}' alt='Crypto-bot' id='sidebar-logo-img'></div>",
            unsafe_allow_html=True,
        )
    env = os.getenv("ENVIRONMENT", "development")
    version = os.getenv("APP_VERSION", "dev")
    color = ENV_COLORS.get(env, "gray")
    st.markdown(f"**Crypto-bot** :{color}[{env}] — `{version}`")


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
        _render_brand_badge()
        st.markdown("---")
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
        _render_brand_badge()
        st.markdown("---")
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
