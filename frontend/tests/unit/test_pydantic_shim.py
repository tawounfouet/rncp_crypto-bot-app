from __future__ import annotations

from pydantic import BaseModel, field_validator


class _DemoModel(BaseModel):
    value: str

    @field_validator("value")
    @classmethod
    def normalize_value(cls, value: str) -> str:
        return value.strip().upper()


def test_internal_field_validators_metadata_is_kept_on_model_class() -> None:
    assert "value" in _DemoModel.__field_validators__


def test_model_dump_hides_internal_metadata_and_keeps_validator_behavior() -> None:
    payload = _DemoModel(value="  btc  ").model_dump()

    assert payload == {"value": "BTC"}
    assert "__field_validators__" not in payload
