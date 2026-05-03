from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CRITICAL_DIRS = [
    ROOT / "src" / "pages",
    ROOT / "src" / "components",
    ROOT / "src" / "layouts",
]
COLOR_LITERAL_PATTERN = re.compile(r"(#[0-9A-Fa-f]{3,8}\b|rgba?\()")
PLOTLY_TEMPLATE_PATTERN = re.compile(r"plotly_(dark|white)")
INLINE_STYLE_PATTERN = re.compile(r"style\s*=")


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for directory in CRITICAL_DIRS:
        files.extend(sorted(directory.rglob("*.py")))
    return files


def test_no_hardcoded_color_literals_outside_theme_layer() -> None:
    offenders: list[str] = []
    for path in _iter_python_files():
        content = path.read_text(encoding="utf-8")
        if COLOR_LITERAL_PATTERN.search(content):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"Hardcoded colors found in critical UI layers: {offenders}"


def test_no_inline_style_attributes_in_critical_ui_layers() -> None:
    offenders: list[str] = []
    for path in _iter_python_files():
        content = path.read_text(encoding="utf-8")
        if INLINE_STYLE_PATTERN.search(content):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"Inline style attributes found in critical UI layers: {offenders}"


def test_no_direct_plotly_template_usage_in_pages_or_components() -> None:
    offenders: list[str] = []
    for path in _iter_python_files():
        content = path.read_text(encoding="utf-8")
        if PLOTLY_TEMPLATE_PATTERN.search(content):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"Direct Plotly template usage found outside theme helpers: {offenders}"
