"""Page Gestion de compte."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from layouts.page_shell import setup_page
from schemas.account import AccountProfile, BinanceCredentialInput, BinanceCredentialStatus
from services.account_service import AccountService
from services.base import ServiceError
from utils.formatters import format_datetime
from utils.streamlit_compat import form_submit_button as compat_form_submit_button


def _render_profile_section(service: AccountService, profile: AccountProfile) -> None:
    render_section_title("Profil utilisateur")
    with st.form("account_profile_form", clear_on_submit=False):
        first_name = st.text_input("Prenom", value=profile.first_name)
        last_name = st.text_input("Nom", value=profile.last_name or "")
        email = st.text_input("Email", value=profile.email)
        save_profile = compat_form_submit_button(
            "Enregistrer le profil",
            type="primary",
            width="stretch",
        )
    if save_profile:
        ok, message = service.update_profile(
            AccountProfile(first_name=first_name, last_name=last_name, email=email)
        )
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()


def _render_binance_status_card(credential_status: BinanceCredentialStatus) -> None:
    render_section_title("Statut des cles Binance")
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    render_status_badge("Binance", "ENABLED" if credential_status.configured else "DISABLED")
    st.caption(
        f"Derniere mise a jour: {format_datetime(credential_status.updated_at)}"
        if credential_status.updated_at
        else "Aucune cle enregistree"
    )
    st.write(f"API key masque: `{credential_status.api_key_masked or 'non configuree'}`")
    st.write(f"API secret masque: `{credential_status.api_secret_masked or 'non configure'}`")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_binance_credentials_form(service: AccountService, title: str) -> None:
    render_section_title(title)
    with st.form("binance_form", clear_on_submit=True):
        api_key = st.text_input("API key")
        api_secret = st.text_input("API secret", type="password")
        password_confirmation = st.text_input("Confirmation mot de passe", type="password")
        save_keys = compat_form_submit_button(
            "Enregistrer les cles Binance",
            type="primary",
            width="stretch",
        )

    if save_keys:
        ok, message = service.save_binance_credentials(
            BinanceCredentialInput(
                api_key=api_key,
                api_secret=api_secret,
                password_confirmation=password_confirmation,
            )
        )
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()


def main() -> None:
    store, _ = setup_page(title="Gestion de compte", icon="👤", page_key="account")
    render_page_header(
        "Gestion de compte",
        "Mise a jour du profil et gestion securisee des cles Binance mockees.",
    )

    service = AccountService(store)
    try:
        profile = service.get_profile()
        credential_status = service.get_binance_status()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    if not credential_status.configured:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown("### Étape prioritaire: configurer Binance")
        st.caption(
            "Votre compte est cree mais le pre-requis Binance n'est pas encore rempli. "
            "Configurez vos cles pour activer toutes les fonctionnalites Spot."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
        _render_binance_credentials_form(service, "Configuration Binance (prioritaire)")
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _render_profile_section(service, profile)
    with right:
        _render_binance_status_card(credential_status)

    if credential_status.configured:
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
        _render_binance_credentials_form(service, "Mettre a jour les credentials Binance")


if __name__ == "__main__":
    main()
