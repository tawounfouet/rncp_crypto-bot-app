from __future__ import annotations

import pandas as pd

from utils.selectors import (
    balances_to_dataframe,
    models_to_dataframe,
    strip_technical_columns,
    top_assets_with_others,
    to_records_df,
)


def test_balances_to_dataframe_empty() -> None:
    frame = balances_to_dataframe([])
    assert list(frame.columns) == ["asset", "free", "locked", "value_usdt"]
    assert frame.empty


def test_top_assets_with_others() -> None:
    df = pd.DataFrame(
        [
            {"asset": f"A{i}", "value_usdt": 100 - i}
            for i in range(12)
        ]
    )
    result = top_assets_with_others(df, top_n=10)
    assert len(result) == 11
    assert result.iloc[-1]["asset"] == "OTHERS"


def test_to_records_df_add_missing_columns() -> None:
    frame = to_records_df([{"a": 1}], ["a", "b"])
    assert list(frame.columns) == ["a", "b"]
    assert frame.iloc[0]["b"] is None


def test_balances_to_dataframe_filters_technical_metadata() -> None:
    frame = balances_to_dataframe(
        [
            {
                "asset": "BTC",
                "free": 1.0,
                "locked": 0.0,
                "value_usdt": 1000.0,
                "__field_validators__": {"asset": []},
            }
        ]
    )
    assert "__field_validators__" not in frame.columns


def test_to_records_df_filters_technical_metadata() -> None:
    frame = to_records_df([{"a": 1, "__field_validators__": {"a": []}}], ["a"])
    assert "__field_validators__" not in frame.columns
    assert frame.iloc[0]["a"] == 1


def test_models_to_dataframe_filters_technical_metadata() -> None:
    class _FakeModel:
        def model_dump(self) -> dict[str, object]:
            return {"asset": "ETH", "value_usdt": 2000.0, "__field_validators__": {"asset": []}}

    frame = models_to_dataframe([_FakeModel()])
    assert "__field_validators__" not in frame.columns
    assert frame.iloc[0]["asset"] == "ETH"


def test_strip_technical_columns_is_idempotent_without_metadata() -> None:
    frame = pd.DataFrame([{"asset": "SOL"}])
    result = strip_technical_columns(frame)
    assert list(result.columns) == ["asset"]
