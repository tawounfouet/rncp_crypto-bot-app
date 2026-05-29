"""Helpers de feedback utilisateur."""

from __future__ import annotations

import streamlit as st


def show_feedback(kind: str, message: str) -> None:
    tone = kind.lower()
    if tone == "success":
        st.success(message)
    elif tone == "warning":
        st.warning(message)
    elif tone == "error":
        st.error(message)
    else:
        st.info(message)
