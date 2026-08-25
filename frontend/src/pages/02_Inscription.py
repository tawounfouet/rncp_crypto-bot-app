"""Page Inscription."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.headers import render_page_header
from layouts.page_shell import setup_page
from schemas.auth import RegisterRequest
from services.auth_service import AuthService
from utils.streamlit_compat import form_submit_button as compat_form_submit_button
from utils.validators import (
    validate_confirm_password,
    validate_email,
    validate_password,
    validate_required,
    validate_username,
)


def main() -> None:
    store, user = setup_page(title="Inscription", icon=":material/person_add:", page_key="signup")
    render_page_header(
        "Inscription",
        "Creez un compte reel via le backend FastAPI et ouvrez la session Streamlit.",
    )

    if user:
        st.info("Vous etes deja connecte. Deconnectez-vous pour creer un autre compte.")
        try:
            st.page_link("pages/03_Portefeuille_Spot.py", label="Aller au portefeuille")
        except Exception:
            st.caption("Aller au portefeuille")
        return

    service = AuthService(store)

    with st.form("register_form", clear_on_submit=False):
        first_name = st.text_input("Prenom *")
        last_name = st.text_input("Nom (optionnel)")
        email = st.text_input("Email *")
        username = st.text_input("Nom d'utilisateur *")
        password = st.text_input("Mot de passe *", type="password")
        confirm_password = st.text_input("Confirmation mot de passe *", type="password")
        st.markdown("---")
        accept_privacy = st.checkbox(
            "J'accepte la politique de confidentialite et le traitement de mes donnees personnelles (RGPD).",
            value=False,
            key="accept_privacy",
        )
        try:
            st.page_link(
                "pages/10_Politique_de_confidentialite.py",
                label="Consulter la politique de confidentialite",
            )
        except Exception:
            st.caption("Consulter la politique de confidentialite")
        submitted = compat_form_submit_button("Creer mon compte", type="primary", width="stretch")

    try:
        st.page_link("app.py", label="Deja inscrit ? Se connecter")
    except Exception:
        st.caption("Deja inscrit ? Se connecter")

    if not submitted:
        return

    checks = [
        validate_required(first_name, "Le prenom"),
        validate_email(email),
        validate_username(username),
        validate_password(password),
        validate_confirm_password(password, confirm_password),
    ]
    for ok, message in checks:
        if not ok:
            show_feedback("error", message)
            return

    if not accept_privacy:
        show_feedback(
            "error",
            "Vous devez accepter la politique de confidentialite et le traitement de vos donnees pour creer un compte.",
        )
        return

    with st.spinner("Creation du compte en cours..."):
        result = service.register(
            RegisterRequest(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                password=password,
                confirm_password=confirm_password,
            )
        )
    if result.success:
        show_feedback("success", f"{result.message} Redirection vers le portefeuille.")
        st.switch_page("pages/03_Portefeuille_Spot.py")
    else:
        show_feedback("error", result.message)


if __name__ == "__main__":
    main()
