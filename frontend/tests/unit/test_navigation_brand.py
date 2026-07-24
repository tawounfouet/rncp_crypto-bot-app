from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

from components.navigation import _logo_data_uri


def test_logo_data_uri_returns_none_when_file_missing(tmp_path):
    _logo_data_uri.cache_clear()
    missing = tmp_path / "does_not_exist.png"
    with patch("components.navigation.LOGO_PATH", missing):
        assert _logo_data_uri() is None
    _logo_data_uri.cache_clear()


def test_logo_data_uri_encodes_file_content(tmp_path):
    _logo_data_uri.cache_clear()
    fake_png = tmp_path / "logo.png"
    fake_png.write_bytes(b"not-a-real-png-but-bytes-are-enough")

    with patch("components.navigation.LOGO_PATH", fake_png):
        result = _logo_data_uri()

    assert result is not None
    assert result.startswith("data:image/png;base64,")
    encoded = result.removeprefix("data:image/png;base64,")
    assert base64.b64decode(encoded) == fake_png.read_bytes()
    _logo_data_uri.cache_clear()


def test_logo_data_uri_is_cached(tmp_path):
    _logo_data_uri.cache_clear()
    fake_png = tmp_path / "logo.png"
    fake_png.write_bytes(b"content-v1")

    with patch("components.navigation.LOGO_PATH", fake_png):
        first = _logo_data_uri()
        fake_png.write_bytes(b"content-v2-should-not-be-picked-up")
        second = _logo_data_uri()

    assert first == second  # lru_cache : le fichier n'est relu qu'une fois par process
    _logo_data_uri.cache_clear()


def test_real_logo_path_resolves_under_frontend_assets():
    from components.navigation import LOGO_PATH

    assert LOGO_PATH.parts[-2:] == ("assets", "crypto_bot_logo.png")
    assert Path(LOGO_PATH).name == "crypto_bot_logo.png"
