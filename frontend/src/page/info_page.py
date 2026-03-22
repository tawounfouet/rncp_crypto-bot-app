import os

import streamlit as st

ENV_COLORS = {
    "development": "blue",
    "staging": "orange",
    "production": "green",
}


def info_page():
    env = os.getenv("ENVIRONMENT", "development")
    version = os.getenv("APP_VERSION", "dev")
    color = ENV_COLORS.get(env, "gray")

    st.title("Crypto-bot")

    st.markdown(f"**Environnement** : :{color}[{env}]")
    st.markdown(f"**Version** : `{version}`")

    if st.button("Retour"):
        st.session_state["page"] = "app"
        st.rerun()
