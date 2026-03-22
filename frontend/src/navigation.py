import streamlit as st
from auth.auth_manager import AuthManager
from page.login_page import login_page
from page.signup_page import signup_page
from page.app import app_page
from page.info_page import info_page
from utils.init_session import init_session, reset_session

init_session()

auth_manager = AuthManager()

if st.session_state["authenticated"]:
    if st.session_state["page"] == "info":
        info_page()
    else:
        app_page(auth_manager)
else:
    if st.session_state["page"] == "login":
        reset_session()
        login_page(auth_manager, guest_mode=True)
    elif st.session_state["page"] == "signup":
        signup_page(auth_manager)
