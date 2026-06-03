"""Badges de statut homogenes."""

from __future__ import annotations

import streamlit as st


def _class_for_status(status: str) -> str:
    token = status.upper()
    if token in {"RUNNING", "ENABLED", "OK", "CONNECTED"}:
        return "status-ok"
    if token in {"PAUSED", "PENDING", "WARNING"}:
        return "status-warning"
    if token in {"STOPPED", "ERROR", "DISABLED", "FAILED"}:
        return "status-error"
    return "status-warning"


def render_status_badge(label: str, status: str) -> None:
    css_class = _class_for_status(status)
    st.markdown(
        f"<span class='status-badge {css_class}'>{label}: {status}</span>",
        unsafe_allow_html=True,
    )
