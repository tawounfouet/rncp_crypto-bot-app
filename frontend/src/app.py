"""Page Connexion."""

from __future__ import annotations

import streamlit as st

from components.alerts import show_feedback
from components.headers import render_page_header
from layouts.page_shell import setup_page
from schemas.auth import LoginRequest
from services.auth_service import AuthService
from utils.streamlit_compat import form_submit_button as compat_form_submit_button
from utils.validators import validate_email, validate_required


def _render_logged_in_state() -> None:
    st.success("Vous etes deja connecte.")
    col1, col2, col3 = st.columns(3)
    with col1:
        try:
            st.page_link("pages/03_Portefeuille_Spot.py", label="Ouvrir Portefeuille Spot")
        except Exception:
            st.caption("Ouvrir Portefeuille Spot")
    with col2:
        try:
            st.page_link("pages/04_Performances_Spot.py", label="Ouvrir Performances Spot")
        except Exception:
            st.caption("Ouvrir Performances Spot")
    with col3:
        try:
            st.page_link("pages/07_Gestion_de_compte.py", label="Ouvrir Gestion de compte")
        except Exception:
            st.caption("Ouvrir Gestion de compte")


def _render_login_form(service: AuthService) -> None:
    with st.form("login_form", clear_on_submit=False):
        email = st.text_input("Email", placeholder="vous@domaine.com")
        password = st.text_input("Mot de passe", type="password")
        submitted = compat_form_submit_button("Se connecter", type="primary", width="stretch")

    try:
        st.page_link("pages/02_Inscription.py", label="Creer un compte")
    except Exception:
        st.caption("Creer un compte")

    if not submitted:
        return

    valid_email, email_msg = validate_email(email)
    valid_pwd, pwd_msg = validate_required(password, "Le mot de passe")
    if not valid_email:
        show_feedback("error", email_msg)
        return
    if not valid_pwd:
        show_feedback("error", pwd_msg)
        return

    with st.spinner("Connexion en cours..."):
        result = service.login(LoginRequest(email=email, password=password))
    if result.success:
        show_feedback("success", result.message)
        st.switch_page("pages/03_Portefeuille_Spot.py")
    else:
        show_feedback("error", result.message)


def main() -> None:
    store, user = setup_page(title="Connexion", icon=":material/lock:", page_key="login")
    render_page_header(
        "Connexion",
        "Authentification reelle via le backend FastAPI. Les ecrans metier restent mockes.",
    )

    if user:
        _render_logged_in_state()
        return

    left, right = st.columns([1.2, 0.8], gap="large")
    with left:
        _render_login_form(AuthService(store))
    with right:
        st.markdown(
            (
                "<div class='premium-card'>"
                "<h4>Connexion</h4>"
                "<p>Deux types de comptes sont disponibles :</p>"
                "<p><strong>• Compte utilisateur</strong><br>"
                "Creez votre compte depuis la page Inscription pour acceder a l'application.</p>"
                "<p><strong>• Compte administrateur de demonstration</strong><br>"
                "Utilisez ce compte pour acceder aux ecrans d'administration.</p>"
                "<p>Email : admin@cryptobot.dev<br>"
                "Mot de passe : Admin123!</p>"
                "<p><strong>Note :</strong><br>"
                "L'authentification et la gestion de session sont reelles.<br>"
                "En dehors de la connexion, de l'inscription et de la session utilisateur, "
                "toutes les autres pages restent en mode demonstration avec des donnees mockees.</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
