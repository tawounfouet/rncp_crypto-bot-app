from __future__ import annotations

import pandas as pd

from components import tables


def test_render_dataframe_filters_technical_metadata_before_ui(monkeypatch) -> None:
    captured: dict[str, pd.DataFrame] = {}

    def fake_dataframe(df: pd.DataFrame, **_: object) -> None:
        captured["df"] = df

    monkeypatch.setattr(tables, "get_theme_mode", lambda: "dark")
    monkeypatch.setattr(tables.st, "dataframe", fake_dataframe)

    frame = pd.DataFrame([{"asset": "BTC", "__field_validators__": {"asset": []}}])
    tables.render_dataframe(frame, key="test_table")

    assert "df" in captured
    assert "__field_validators__" not in captured["df"].columns
    assert captured["df"].iloc[0]["asset"] == "BTC"


def test_render_dataframe_uses_themed_html_table_in_light_mode(monkeypatch) -> None:
    calls: dict[str, object] = {"dataframe_called": False}

    def fake_dataframe(*_: object, **__: object) -> None:
        calls["dataframe_called"] = True

    def fake_markdown(content: str, **_: object) -> None:
        calls["html"] = content

    monkeypatch.setattr(tables, "get_theme_mode", lambda: "light")
    monkeypatch.setattr(tables.st, "dataframe", fake_dataframe)
    monkeypatch.setattr(tables.st, "markdown", fake_markdown)

    frame = pd.DataFrame([{"asset": "ETH", "__field_validators__": {"asset": []}, "value_usdc": 1234}])
    tables.render_dataframe(frame, key="light_table", height=200)

    assert calls["dataframe_called"] is False
    assert "theme-table-wrapper" in str(calls.get("html", ""))
    assert "__field_validators__" not in str(calls.get("html", ""))
