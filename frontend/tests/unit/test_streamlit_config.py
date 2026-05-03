from __future__ import annotations

from pathlib import Path


def test_sidebar_navigation_default_streamlit_disabled() -> None:
    config_path = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"
    content = config_path.read_text(encoding="utf-8")
    assert "showSidebarNavigation = false" in content


def test_dark_theme_remains_default_in_streamlit_config() -> None:
    config_path = Path(__file__).resolve().parents[2] / ".streamlit" / "config.toml"
    content = config_path.read_text(encoding="utf-8")
    assert 'base = "dark"' in content


def test_pytest_cache_dir_is_configured_to_temp_path() -> None:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    assert 'cache_dir = "%TEMP%/crypto-bot-app-pytest-cache"' in content
