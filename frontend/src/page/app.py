import os

import streamlit as st
from utils.init_session import reset_session

ENV_COLORS = {
    "development": "blue",
    "staging": "orange",
    "production": "green",
}


def app_page(auth_manager):
    env = os.getenv("ENVIRONMENT", "development")
    color = ENV_COLORS.get(env, "gray")

    with st.sidebar:
        if st.session_state["guest_mode"]:
            st.subheader("Guest Mode")

            if st.button("Login"):
                reset_session()
                st.rerun()

        else:
            user_data = st.session_state.get("user_data")
            if user_data:
                st.subheader(f"Welcome, {user_data.get('username', '')}")

            if st.button("Logout"):
                auth_manager.logout()
                reset_session()
                st.rerun()

        st.divider()
        st.markdown(f"**Crypto-bot** :{color}[{env}]")
        if st.button("Info"):
            st.session_state["page"] = "info"
            st.rerun()

    st.title("App Page")
    st.write("Hello World")
