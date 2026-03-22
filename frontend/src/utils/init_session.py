import streamlit as st


def init_session():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "page" not in st.session_state:
        st.session_state["page"] = "login"
    if "guest_mode" not in st.session_state:
        st.session_state["guest_mode"] = False
    if "access_token" not in st.session_state:
        st.session_state["access_token"] = None
    if "refresh_token" not in st.session_state:
        st.session_state["refresh_token"] = None
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = None


def reset_session():
    st.session_state["authenticated"] = False
    st.session_state["page"] = "login"
    st.session_state["guest_mode"] = False
    st.session_state["access_token"] = None
    st.session_state["refresh_token"] = None
    st.session_state["user_data"] = None
