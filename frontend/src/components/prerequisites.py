"""Composants de rendu des pre-requis manquants."""

from __future__ import annotations

import streamlit as st

from prerequisites.exchange import missing_copy_for_page
from utils.constants import ACCOUNT_SETTINGS_PAGE_PATH, EXCHANGE_SETUP_CTA_LABEL
from utils.streamlit_compat import button as compat_button


def render_exchange_prerequisite_state(page_key: str, cta_key: str) -> None:
    title, message = missing_copy_for_page(page_key)
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    st.markdown(f"### {title}")
    st.caption(message)
    st.warning("Ce module reste indisponible tant que le pré-requis n'est pas rempli.")
    if compat_button(EXCHANGE_SETUP_CTA_LABEL, key=cta_key, type="primary", width="stretch"):
        st.switch_page(ACCOUNT_SETTINGS_PAGE_PATH)
    st.markdown("</div>", unsafe_allow_html=True)
