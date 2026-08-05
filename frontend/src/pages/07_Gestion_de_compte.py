"""Page Gestion de compte."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from layouts.page_shell import setup_page
from schemas.account import AccountProfile, ApiCredentialInput
from services.account_service import AccountService
from services.base import ServiceError
from utils.streamlit_compat import button as compat_button
from utils.streamlit_compat import form_submit_button as compat_form_submit_button

SUPPORTED_EXCHANGES = ["binance", "kraken", "bybit", "coinbase", "okx"]


def _render_profile_section(service: AccountService, profile: AccountProfile) -> None:
    render_section_title("Profil utilisateur")
    with st.form("account_profile_form", clear_on_submit=False):
        first_name = st.text_input("Prenom", value=profile.first_name)
        last_name = st.text_input("Nom", value=profile.last_name or "")
        email = st.text_input("Email", value=profile.email)
        save_profile = compat_form_submit_button(
            "Enregistrer le profil", type="primary", width="stretch"
        )
    if save_profile:
        ok, message = service.update_profile(
            AccountProfile(first_name=first_name, last_name=last_name, email=email)
        )
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()


def _render_credentials_table(service: AccountService) -> None:
    render_section_title("Clefs API enregistrees")
    credentials = service.list_credentials()

    if not credentials:
        st.info("Aucune clef API enregistree. Ajoutez-en une ci-dessous.")
        return

    for cred in credentials:
        col_label, col_exchange, col_masked, col_primary, col_del = st.columns(
            [2.5, 1.5, 2, 1.5, 1]
        )
        with col_label:
            label_text = f"**{cred.label}**"
            if cred.is_primary:
                label_text += " ★"
            st.write(label_text)
            if cred.created_at:
                st.caption(cred.created_at[:10])
        with col_exchange:
            render_status_badge("Exchange", cred.exchange.upper())
        with col_masked:
            st.code(cred.api_key_masked, language=None)
        with col_primary:
            if cred.is_primary:
                st.caption("Principale")
            else:
                if compat_button("Définir principale", key=f"primary_{cred.id}"):
                    ok, msg = service.set_primary_credential(cred.id)
                    show_feedback("success" if ok else "error", msg)
                    if ok:
                        st.rerun()
        with col_del:
            confirm_key = f"confirm_del_{cred.id}"
            if st.session_state.get(confirm_key):
                if compat_button("Confirmer", key=f"do_del_{cred.id}"):
                    ok, msg = service.delete_credential(cred.id)
                    show_feedback("success" if ok else "error", msg)
                    st.session_state[confirm_key] = False
                    if ok:
                        st.rerun()
                if compat_button("Annuler", key=f"cancel_del_{cred.id}"):
                    st.session_state[confirm_key] = False
                    st.rerun()
            else:
                if compat_button("Supprimer", key=f"del_{cred.id}"):
                    st.session_state[confirm_key] = True
                    st.rerun()
        st.divider()


def _render_add_credential_form(service: AccountService) -> None:
    render_section_title("Ajouter une clef API")
    with st.form("add_credential_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            label = st.text_input("Label (ex: Binance Spot principal)", max_chars=100)
            exchange = st.selectbox("Exchange", options=SUPPORTED_EXCHANGES)
        with col2:
            api_key = st.text_input("API key")
            api_secret = st.text_input("API secret", type="password")
        submitted = compat_form_submit_button(
            "Enregistrer la clef", type="primary", width="stretch"
        )

    if submitted:
        ok, message = service.add_credential(
            ApiCredentialInput(
                label=label, exchange=exchange, api_key=api_key, api_secret=api_secret
            )
        )
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()


def main() -> None:
    store, _ = setup_page(title="Gestion de compte", icon="👤", page_key="account")
    render_page_header(
        "Gestion de compte",
        "Profil, clefs API multi-exchanges (chiffrees en base). Plusieurs clefs par exchange supportees.",
    )

    service = AccountService(store)
    try:
        profile = service.get_profile()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    # Check if at least one Binance key exists
    credentials = service.list_credentials()
    has_binance = any(c.exchange == "binance" for c in credentials)
    if not has_binance:
        with st.container(border=True):
            st.markdown("### Etape prioritaire: configurer une clef Binance")
            st.caption(
                "Ajoutez au moins une clef Binance pour activer le portefeuille et les bots Spot."
            )
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _render_profile_section(service, profile)
    with right:
        with st.container(border=True):
            st.markdown(f"**Clefs enregistrees:** {len(credentials)}")
            binance_count = sum(1 for c in credentials if c.exchange == "binance")
            if binance_count:
                render_status_badge("Binance", "ENABLED")
                st.caption(f"{binance_count} clef(s) Binance")
            else:
                render_status_badge("Binance", "DISABLED")
                st.caption("Aucune clef Binance")

    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    _render_credentials_table(service)
    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
    _render_add_credential_form(service)


if __name__ == "__main__":
    main()
