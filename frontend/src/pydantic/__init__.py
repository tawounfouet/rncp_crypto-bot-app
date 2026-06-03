"""Minimal pydantic-compatible shim for offline execution.

This lightweight module supports only the subset used by this frontend:
- BaseModel
- Field(default=..., default_factory=...)
- field_validator(...)
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar, get_origin


@dataclass
class _FieldInfo:
    default: Any = ...
    default_factory: Callable[[], Any] | None = None


def Field(default: Any = ..., default_factory: Callable[[], Any] | None = None, **_: Any) -> Any:  # noqa: N802
    return _FieldInfo(default=default, default_factory=default_factory)


def field_validator(*field_names: str):
    def decorator(func: Any) -> Any:
        target = func.__func__ if isinstance(func, classmethod) else func
        target.__field_validator_fields__ = field_names
        return func

    return decorator


class BaseModel:
    __field_validators__: ClassVar[dict[str, list[Callable[..., Any]]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        validators: dict[str, list[Callable[..., Any]]] = {}
        for name, member in cls.__dict__.items():
            target = member.__func__ if isinstance(member, classmethod) else member
            fields = getattr(target, "__field_validator_fields__", None)
            if not fields:
                continue
            callable_member = getattr(cls, name)
            for field_name in fields:
                validators.setdefault(field_name, []).append(callable_member)
        cls.__field_validators__ = validators

    def __init__(self, **data: Any) -> None:
        annotations = _collect_annotations(self.__class__)
        for field_name in annotations:
            value = self._resolve_value(field_name, data)
            setattr(self, field_name, value)
        self._run_field_validators()
        extra = {k: v for k, v in data.items() if k not in annotations}
        if extra:
            unknown = ", ".join(sorted(extra))
            raise TypeError(f"Unexpected fields: {unknown}")

    def _resolve_value(self, field_name: str, data: dict[str, Any]) -> Any:
        if field_name in data:
            return data[field_name]

        attr = getattr(self.__class__, field_name, ...)
        if isinstance(attr, _FieldInfo):
            if attr.default_factory is not None:
                return attr.default_factory()
            if attr.default is ...:
                raise TypeError(f"Missing required field: {field_name}")
            return copy.deepcopy(attr.default)

        if attr is not ...:
            return copy.deepcopy(attr)
        raise TypeError(f"Missing required field: {field_name}")

    def _run_field_validators(self) -> None:
        for field_name, callbacks in self.__class__.__field_validators__.items():
            if not hasattr(self, field_name):
                continue
            value = getattr(self, field_name)
            for callback in callbacks:
                value = callback(value)
            setattr(self, field_name, value)

    def model_dump(self) -> dict[str, Any]:
        annotations = _collect_annotations(self.__class__)
        return {name: getattr(self, name) for name in annotations}

    def model_copy(self, update: dict[str, Any] | None = None) -> BaseModel:
        payload = self.model_dump()
        if update:
            payload.update(update)
        return self.__class__(**payload)

    def __repr__(self) -> str:
        fields = ", ".join(f"{k}={v!r}" for k, v in self.model_dump().items())
        return f"{self.__class__.__name__}({fields})"


def _collect_annotations(model: type[BaseModel]) -> dict[str, Any]:
    collected: dict[str, Any] = {}
    for cls in reversed(model.mro()):
        annotations = getattr(cls, "__annotations__", {})
        for field_name, annotation in annotations.items():
            if _is_technical_field(field_name):
                continue
            if _is_classvar_annotation(annotation):
                continue
            collected[field_name] = annotation
    return collected


def _is_technical_field(field_name: str) -> bool:
    return field_name.startswith("__") and field_name.endswith("__")


def _is_classvar_annotation(annotation: Any) -> bool:
    if get_origin(annotation) is ClassVar:
        return True
    if not isinstance(annotation, str):
        return False
    normalized = annotation.replace("typing.", "")
    return normalized == "ClassVar" or normalized.startswith("ClassVar[")
