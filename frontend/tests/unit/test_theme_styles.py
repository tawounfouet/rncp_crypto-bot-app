from __future__ import annotations

from theme.styles import build_global_css
from theme.tokens import get_theme_tokens


def test_build_global_css_contains_dark_theme_marker_and_tokens() -> None:
    css = build_global_css("dark")
    dark = get_theme_tokens("dark")

    assert "theme-mode:dark" in css
    assert dark["bg_main"] in css
    assert dark["txt_primary"] in css
    assert dark["sidebar_bg"] in css
    assert dark["sidebar_nav_active_bg"] in css
    assert dark["button_secondary_bg"] in css
    assert dark["dropdown_bg"] in css
    assert dark["dropdown_selected_bg"] in css
    assert 'section[data-testid="stSidebar"]' in css
    assert 'header[data-testid="stHeader"]' in css


def test_build_global_css_contains_light_theme_marker_and_tokens() -> None:
    css = build_global_css("light")
    light = get_theme_tokens("light")

    assert "theme-mode:light" in css
    assert light["bg_main"] in css
    assert light["txt_primary"] in css
    assert light["table_header_bg"] in css
    assert light["sidebar_bg"] in css
    assert light["sidebar_nav_active_bg"] in css
    assert light["button_secondary_bg"] in css
    assert light["alert_info_bg"] in css
    assert light["dropdown_bg"] in css
    assert light["dropdown_selected_bg"] in css
    assert light["native_color_scheme"] in css


def test_build_global_css_styles_metric_and_number_controls() -> None:
    css = build_global_css("light")
    assert '[data-testid="stMetricValue"]' in css
    assert 'button[data-testid="stNumberInputStepUp"]' in css
    assert '.stFormSubmitButton > button' in css
    assert ".theme-table-wrapper" in css


def test_build_global_css_styles_select_container_and_virtual_dropdown_portal() -> None:
    css = build_global_css("light")
    assert 'div[data-baseweb="select"] > div' in css
    assert 'div[data-baseweb="popover"]' in css
    assert '[data-testid="stSelectboxVirtualDropdown"]' in css
    assert '[role="listbox"]' in css
    assert '[role="option"][aria-selected="true"]' in css
