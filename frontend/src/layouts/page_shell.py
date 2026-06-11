"""Shell commun des pages Streamlit."""

from __future__ import annotations

import streamlit as st

from components.navigation import render_private_sidebar, render_public_sidebar
from navigation.rules import can_access
from services.auth_service import AuthService
from state.session import get_store, get_theme_mode, is_binance_synced
from theme.styles import apply_global_styles


def setup_page(
    title: str,
    icon: str,
    page_key: str,
) -> tuple:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    apply_global_styles(get_theme_mode())

    store = get_store()
    auth_service = AuthService(store)
    user = auth_service.ensure_authenticated_user()

    if user is None:
        render_public_sidebar()
        if not can_access(page_key, user):
            st.warning("Veuillez vous connecter pour acceder a cette page.")
            try:
                st.page_link("app.py", label="Aller a la page Connexion")
            except Exception:
                st.caption("Aller a la page Connexion")
            st.stop()
        return store, user

    # Synchronise le statut Binance une seule fois par session
    if not is_binance_synced():
        from services.account_service import AccountService

        AccountService(store).get_binance_status()

    do_logout = render_private_sidebar(store, user)
    if do_logout:
        auth_service.logout()
        st.success("Session fermee.")
        st.switch_page("app.py")

    if not can_access(page_key, user):
        st.error("Cette page est reservee aux administrateurs.")
        st.stop()

    return store, user
