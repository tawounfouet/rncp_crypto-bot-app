"""Composants de titres et sections."""

from __future__ import annotations

import streamlit as st


def render_page_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f"<h1 class='page-title'>{title}</h1>", unsafe_allow_html=True)
    if subtitle:
        st.markdown(f"<p class='page-subtitle'>{subtitle}</p>", unsafe_allow_html=True)


def render_section_title(title: str, caption: str | None = None) -> None:
    st.subheader(title)
    if caption:
        st.caption(caption)
