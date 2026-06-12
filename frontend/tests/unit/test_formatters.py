from __future__ import annotations

from datetime import datetime

from utils.formatters import bool_to_label, format_currency, format_datetime, format_pct, mask_secret


def test_format_currency() -> None:
    assert format_currency(12345.6) == "12 345.60 USDC"


def test_format_pct() -> None:
    assert format_pct(2.5) == "+2.50%"
    assert format_pct(-1.2) == "-1.20%"


def test_format_datetime_none() -> None:
    assert format_datetime(None) == "-"


def test_format_datetime_value() -> None:
    dt = datetime(2026, 1, 2, 3, 4, 5)
    assert format_datetime(dt) == "2026-01-02 03:04:05"


def test_mask_secret() -> None:
    assert mask_secret("ABCD1234ZZZZ") == "ABCD****ZZZZ"
    assert mask_secret("ABC") == "***"


def test_bool_to_label() -> None:
    assert bool_to_label(True) == "Oui"
    assert bool_to_label(False) == "Non"
