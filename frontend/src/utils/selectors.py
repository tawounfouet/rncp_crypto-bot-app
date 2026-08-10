"""Selectors de donnees pour graphes et tableaux."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

TECHNICAL_METADATA_KEYS: frozenset[str] = frozenset({"__field_validators__"})


def sanitize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in TECHNICAL_METADATA_KEYS}


def sanitize_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [sanitize_record(record) for record in records]


def strip_technical_columns(frame: pd.DataFrame) -> pd.DataFrame:
    columns_to_drop = [column for column in TECHNICAL_METADATA_KEYS if column in frame.columns]
    if not columns_to_drop:
        return frame
    return frame.drop(columns=columns_to_drop)


def models_to_dataframe(items: list[Any]) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "model_dump"):
            payload = item.model_dump()
        elif isinstance(item, Mapping):
            payload = dict(item)
        else:
            raise TypeError("models_to_dataframe accepte des mappings ou objets avec model_dump().")

        if not isinstance(payload, Mapping):
            raise TypeError("model_dump() doit retourner un mapping.")
        records.append(sanitize_record(payload))
    return strip_technical_columns(pd.DataFrame(records))


def balances_to_dataframe(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=["asset", "free", "locked", "value_usdc"])
    return strip_technical_columns(pd.DataFrame(sanitize_records(rows)))


def top_assets_with_others(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["asset", "value_usdc"])
    frame = df.sort_values("value_usdc", ascending=False).reset_index(drop=True)
    top = frame.head(top_n).copy()
    if len(frame) <= top_n:
        return top[["asset", "value_usdc"]]
    others_value = frame.iloc[top_n:]["value_usdc"].sum()
    others = pd.DataFrame([{"asset": "OTHERS", "value_usdc": others_value}])
    return pd.concat([top[["asset", "value_usdc"]], others], ignore_index=True)


def to_records_df(records: list[dict], columns: list[str]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=columns)
    frame = strip_technical_columns(pd.DataFrame(sanitize_records(records)))
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]
