from __future__ import annotations

from theme.plotly import (
    pie_color_sequence,
    plotly_grid_color,
    plotly_line_color,
    plotly_template,
    themed_axis,
    themed_layout,
    themed_rangeslider,
)
from theme.tokens import get_theme_tokens


def test_plotly_template_switches_by_theme_mode() -> None:
    assert plotly_template("dark") == "plotly_dark"
    assert plotly_template("light") == "plotly_white"


def test_plotly_line_color_uses_theme_accent() -> None:
    assert plotly_line_color("dark") == get_theme_tokens("dark")["accent"]
    assert plotly_line_color("light") == get_theme_tokens("light")["accent"]


def test_themed_layout_uses_theme_font_color() -> None:
    dark_layout = themed_layout("dark")
    light_layout = themed_layout("light")

    assert dark_layout["font"]["color"] == get_theme_tokens("dark")["txt_primary"]
    assert light_layout["font"]["color"] == get_theme_tokens("light")["txt_primary"]
    assert dark_layout["hoverlabel"]["font"]["color"] == get_theme_tokens("dark")["txt_primary"]
    assert light_layout["hoverlabel"]["font"]["color"] == get_theme_tokens("light")["txt_primary"]


def test_themed_axis_uses_grid_and_tick_colors_from_theme() -> None:
    dark_axis = themed_axis("dark")
    light_axis = themed_axis("light")

    assert dark_axis["gridcolor"] == plotly_grid_color("dark")
    assert light_axis["gridcolor"] == plotly_grid_color("light")
    assert dark_axis["tickfont"]["color"] == get_theme_tokens("dark")["txt_secondary"]
    assert light_axis["tickfont"]["color"] == get_theme_tokens("light")["txt_secondary"]


def test_themed_layout_background_is_light_only_in_light_mode() -> None:
    dark_layout = themed_layout("dark")
    light_layout = themed_layout("light")
    assert dark_layout["paper_bgcolor"] == "rgba(0,0,0,0)"
    assert light_layout["paper_bgcolor"] == get_theme_tokens("light")["bg_surface"]


def test_themed_rangeslider_uses_theme_surface_and_axis_border() -> None:
    dark_slider = themed_rangeslider("dark")
    light_slider = themed_rangeslider("light")

    assert dark_slider["visible"] is True
    assert light_slider["visible"] is True
    assert dark_slider["bgcolor"] == get_theme_tokens("dark")["bg_surface"]
    assert light_slider["bgcolor"] == get_theme_tokens("light")["bg_surface"]


def test_pie_color_sequence_is_non_empty_for_both_modes() -> None:
    assert len(pie_color_sequence("dark")) >= 6
    assert len(pie_color_sequence("light")) >= 6
