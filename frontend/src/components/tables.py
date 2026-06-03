"""Wrapper uniforme pour les tableaux."""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from state.session import get_theme_mode
from utils.selectors import strip_technical_columns
from utils.streamlit_compat import dataframe as compat_dataframe


def _to_display_value(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def _render_html_table(df: pd.DataFrame, key: str, height: int) -> None:
    header_html = "".join(f"<th>{html.escape(str(column))}</th>" for column in df.columns)
    rows_html: list[str] = []
    for _, row in df.iterrows():
        cells = "".join(
            f"<td>{html.escape(_to_display_value(value))}</td>" for value in row.tolist()
        )
        rows_html.append(f"<tr>{cells}</tr>")

    table_html = (
        f"<div class='theme-table-wrapper' data-theme-table='{html.escape(key)}'>"
        "<table class='theme-table'>"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        "</table>"
        "</div>"
    )
    with st.container(height=height):
        st.markdown(table_html, unsafe_allow_html=True)


def render_dataframe(df: pd.DataFrame, key: str, height: int = 320) -> None:
    safe_df = strip_technical_columns(df)
    if get_theme_mode() == "light":
        _render_html_table(safe_df, key=key, height=height)
        return
    compat_dataframe(
        safe_df,
        key=key,
        width="stretch",
        height=height,
        hide_index=True,
    )
