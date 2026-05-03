"""Composants de KPI cards."""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass
class KpiItem:
    label: str
    value: str
    delta: str | None = None


def render_kpi_cards(items: list[KpiItem], columns: int = 4) -> None:
    if not items:
        return
    cols = st.columns(columns)
    for idx, item in enumerate(items):
        col = cols[idx % columns]
        with col:
            st.markdown(
                (
                    "<div class='premium-card'>"
                    f"<div class='kpi-label'>{item.label}</div>"
                    f"<div class='kpi-value'>{item.value}</div>"
                    f"<div class='kpi-delta'>{item.delta or ''}</div>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
