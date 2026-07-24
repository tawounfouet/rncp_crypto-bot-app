"""Page Gestion de compte."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.badges import render_status_badge
from components.headers import render_page_header, render_section_title
from layouts.page_shell import setup_page
from schemas.account import AccountProfile, ExchangeCredentialInput, ExchangeCredentialStatus
from services.account_service import AccountService
from services.base import ServiceError
from state.session import get_selected_exchange, set_selected_exchange
from utils.constants import EXCHANGE_CATALOG
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


def _render_exchange_selector() -> str:
    render_section_title("Exchange")
    exchange_ids = list(EXCHANGE_CATALOG.keys())
    current = get_selected_exchange()
    selected = st.selectbox(
        "Exchange actif",
        options=exchange_ids,
        index=exchange_ids.index(current) if current in exchange_ids else 0,
        format_func=lambda eid: EXCHANGE_CATALOG.get(eid, eid),
        help="L'exchange utilise pour la collecte de donnees et l'execution de vos ordres.",
    )
    if selected != current:
        set_selected_exchange(selected)
        st.rerun()
    return selected


def _render_exchange_status_card(
    exchange: str, credential_status: ExchangeCredentialStatus
) -> None:
    render_section_title(f"Statut des cles {EXCHANGE_CATALOG.get(exchange, exchange)}")
    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    render_status_badge(
        EXCHANGE_CATALOG.get(exchange, exchange),
        "ENABLED" if credential_status.configured else "DISABLED",
    )
    st.caption(
        f"Derniere mise a jour: {format_datetime(credential_status.updated_at)}"
        if credential_status.updated_at
        else "Aucune cle enregistree"
    )
    st.write(f"API key masque: `{credential_status.api_key_masked or 'non configuree'}`")
    st.write(f"API secret masque: `{credential_status.api_secret_masked or 'non configure'}`")
    st.markdown("</div>", unsafe_allow_html=True)


def _render_exchange_credentials_form(service: AccountService, exchange: str, title: str) -> None:
    render_section_title(title)
    with st.form(f"exchange_form_{exchange}", clear_on_submit=True):
        api_key = st.text_input("API key")
        api_secret = st.text_input("API secret", type="password")
        save_keys = compat_form_submit_button(
            f"Enregistrer les cles {EXCHANGE_CATALOG.get(exchange, exchange)}",
            type="primary",
            width="stretch",
        )

    if save_keys:
        ok, message = service.save_exchange_credentials(
            ExchangeCredentialInput(
                exchange=exchange,
                api_key=api_key,
                api_secret=api_secret,
            )
        )
        show_feedback("success" if ok else "error", message)
        if ok:
            st.rerun()


def _render_configured_exchanges_section(service: AccountService, selected_exchange: str) -> None:
    render_section_title("Mes clés API enregistrées")
    configured = service.list_configured_exchanges()

    if not configured:
        st.caption("Aucune clé API enregistree pour le moment.")
        return

    st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
    for exchange in configured:
        label = EXCHANGE_CATALOG.get(exchange, exchange)
        row_left, row_mid, row_right = st.columns([2, 1, 1.2])
        with row_left:
            st.write(f"**{label}**" + (" (actif)" if exchange == selected_exchange else ""))
        with row_mid:
            render_status_badge(label, "ENABLED")
        with row_right:
            confirm = st.checkbox("Confirmer", key=f"confirm_delete_{exchange}")
            if st.button("Supprimer", key=f"delete_{exchange}", disabled=not confirm):
                ok, message = service.delete_exchange_credentials(exchange)
                show_feedback("success" if ok else "error", message)
                if ok:
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def main() -> None:
    store, _ = setup_page(title="Gestion de compte", icon="👤", page_key="account")
    render_page_header(
        "Gestion de compte",
        "Mise a jour du profil et gestion securisee des cles d'exchange (chiffrees en base).",
    )

    service = AccountService(store)
    try:
        profile = service.get_profile()
    except ServiceError as exc:
        show_feedback("error", str(exc))
        return

    selected_exchange = _render_exchange_selector()
    exchange_label = EXCHANGE_CATALOG.get(selected_exchange, selected_exchange)
    credential_status = service.get_exchange_status(selected_exchange)

    _render_configured_exchanges_section(service, selected_exchange)
    st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)

    if not credential_status.configured:
        st.markdown("<div class='premium-card'>", unsafe_allow_html=True)
        st.markdown(f"### Étape prioritaire: configurer {exchange_label}")
        st.caption(
            f"Votre compte est cree mais le pre-requis {exchange_label} n'est pas encore rempli. "
            "Configurez vos cles pour activer toutes les fonctionnalites Spot."
        )
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
        _render_exchange_credentials_form(
            service, selected_exchange, f"Configuration {exchange_label} (prioritaire)"
        )
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)

    left, right = st.columns([1.1, 1], gap="large")
    with left:
        _render_profile_section(service, profile)
    with right:
        _render_exchange_status_card(selected_exchange, credential_status)

    if credential_status.configured:
        st.markdown("<hr class='divider-soft'/>", unsafe_allow_html=True)
        _render_exchange_credentials_form(
            service, selected_exchange, f"Mettre a jour les credentials {exchange_label}"
        )


if __name__ == "__main__":
    main()
