from __future__ import annotations

from theme.tokens import get_theme_tokens


def _hex_to_rgb(hex_value: str) -> tuple[float, float, float]:
    token = hex_value.strip().lstrip("#")
    if len(token) == 3:
        token = "".join(ch * 2 for ch in token)
    if len(token) != 6:
        raise ValueError(f"Unsupported color format: {hex_value}")
    r = int(token[0:2], 16) / 255
    g = int(token[2:4], 16) / 255
    b = int(token[4:6], 16) / 255
    return r, g, b


def _linearize(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(hex_value: str) -> float:
    r, g, b = _hex_to_rgb(hex_value)
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def _contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a = _luminance(hex_a)
    lum_b = _luminance(hex_b)
    lighter = max(lum_a, lum_b)
    darker = min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def test_primary_text_contrast_is_accessible_on_main_background() -> None:
    for mode in ("dark", "light"):
        tokens = get_theme_tokens(mode)
        assert _contrast_ratio(tokens["txt_primary"], tokens["bg_main"]) >= 4.5


def test_secondary_text_contrast_is_readable_on_surface_background() -> None:
    for mode in ("dark", "light"):
        tokens = get_theme_tokens(mode)
        assert _contrast_ratio(tokens["txt_secondary"], tokens["bg_surface"]) >= 3.0


def test_theme_surfaces_and_borders_are_distinct_between_modes() -> None:
    dark = get_theme_tokens("dark")
    light = get_theme_tokens("light")

    assert dark["bg_main"] != light["bg_main"]
    assert dark["bg_card"] != light["bg_card"]
    assert dark["border"] != light["border"]
