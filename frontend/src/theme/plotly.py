"""Helpers Plotly pour theming coherent."""

from __future__ import annotations

from typing import Any

from theme.manager import ThemeMode
from theme.tokens import get_theme_tokens

_PIE_COLORS: dict[ThemeMode, list[str]] = {
    "dark": [
        "#11CDEF",
        "#26F7A6",
        "#4DA8FF",
        "#8B7CFF",
        "#FF5A7A",
        "#F6C343",
        "#60D7FF",
        "#9FFFE3",
        "#A8B8FF",
        "#FF95AA",
    ],
    "light": [
        "#0EA5C6",
        "#11B78A",
        "#2F6AE6",
        "#5F83EF",
        "#D64266",
        "#B7791F",
        "#55B5D8",
        "#6FCFAF",
        "#8CA3EA",
        "#DF8199",
    ],
}


def plotly_template(mode: ThemeMode) -> str:
    if mode == "light":
        return "plotly_white"
    return "plotly_dark"


def plotly_line_color(mode: ThemeMode) -> str:
    return get_theme_tokens(mode)["accent"]


def plotly_grid_color(mode: ThemeMode) -> str:
    if mode == "light":
        return "rgba(113, 138, 172, 0.24)"
    return "rgba(120, 144, 180, 0.26)"


def plotly_axis_line_color(mode: ThemeMode) -> str:
    if mode == "light":
        return "rgba(121, 146, 178, 0.42)"
    return "rgba(110, 133, 167, 0.52)"


def plotly_hover_background(mode: ThemeMode) -> str:
    if mode == "light":
        return "rgba(250, 252, 255, 0.98)"
    return "rgba(18, 27, 42, 0.96)"


def pie_color_sequence(mode: ThemeMode) -> list[str]:
    return _PIE_COLORS[mode]


def themed_axis(mode: ThemeMode, **overrides: Any) -> dict[str, Any]:
    tokens = get_theme_tokens(mode)
    axis: dict[str, Any] = {
        "showgrid": True,
        "gridcolor": plotly_grid_color(mode),
        "linecolor": plotly_axis_line_color(mode),
        "zerolinecolor": plotly_grid_color(mode),
        "tickfont": {"color": tokens["txt_secondary"]},
        "title": {"font": {"color": tokens["txt_primary"]}},
    }
    axis.update(overrides)
    return axis


def themed_rangeslider(mode: ThemeMode) -> dict[str, Any]:
    tokens = get_theme_tokens(mode)
    return {
        "visible": True,
        "bgcolor": tokens["bg_surface"],
        "bordercolor": plotly_axis_line_color(mode),
        "thickness": 0.11,
    }


def themed_layout(mode: ThemeMode, **overrides: Any) -> dict[str, Any]:
    tokens = get_theme_tokens(mode)
    background = tokens["bg_surface"] if mode == "light" else "rgba(0,0,0,0)"
    base_layout: dict[str, Any] = {
        "template": plotly_template(mode),
        "paper_bgcolor": background,
        "plot_bgcolor": background,
        "font": {"color": tokens["txt_primary"]},
        "legend": {
            "font": {"color": tokens["txt_secondary"]},
            "title": {"font": {"color": tokens["txt_primary"]}},
        },
        "hoverlabel": {
            "bgcolor": plotly_hover_background(mode),
            "font": {"color": tokens["txt_primary"]},
            "bordercolor": plotly_axis_line_color(mode),
        },
    }
    base_layout.update(overrides)
    return base_layout
