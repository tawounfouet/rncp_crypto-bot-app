import os

import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

ENV_COLORS = {
    "development": "blue",
    "staging": "orange",
    "production": "green",
}


def login_page(auth_manager, guest_mode=False):
    env = os.getenv("ENVIRONMENT", "development")
    version = os.getenv("APP_VERSION", "dev")
    color = ENV_COLORS.get(env, "gray")
    st.caption(f"**Crypto-bot** :{color}[{env}] `{version}`")

    with st.empty().container(border=True):
        col1, _, col2 = st.columns([10, 1, 10])

        with col1:
            st.write("")
            st.write("")
            st.image(os.path.join(DATA_DIR, "crypto.com_bot.png"))

        with col2:
            st.title("Login Page")

            username = st.text_input("Username or E-mail")
            password = st.text_input("Password", type="password")

            if st.button("Login"):
                if not (username and password):
                    st.error("Please provide username/email and password")
                else:
                    with st.spinner("Logging in..."):
                        success, message = auth_manager.login(username, password)
                    if success:
                        st.session_state["page"] = "app"
                        st.rerun()
                    else:
                        st.error(message)

            if st.button("Sign Up"):
                st.session_state["page"] = "signup"
                st.rerun()

            if guest_mode:
                if st.button("Continue as Guest"):
                    st.session_state["guest_mode"] = True
                    st.session_state["authenticated"] = True
                    st.session_state["page"] = "app"
                    st.rerun()
