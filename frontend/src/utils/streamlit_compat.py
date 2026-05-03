"""Compat helpers for Streamlit width APIs across 1.x releases."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

import streamlit as st

WidthMode = Literal["stretch", "content"]
ReturnType = TypeVar("ReturnType")


def button(label: str, *args: Any, width: WidthMode = "content", **kwargs: Any) -> bool:
    return _call_with_width(st.button, label, *args, width=width, **kwargs)


def form_submit_button(
    label: str = "Submit",
    *args: Any,
    width: WidthMode = "content",
    **kwargs: Any,
) -> bool:
    return _call_with_width(st.form_submit_button, label, *args, width=width, **kwargs)


def plotly_chart(
    figure_or_data: Any, *args: Any, width: WidthMode = "stretch", **kwargs: Any
) -> Any:
    return _call_with_width(st.plotly_chart, figure_or_data, *args, width=width, **kwargs)


def dataframe(data: Any, *args: Any, width: WidthMode = "stretch", **kwargs: Any) -> Any:
    return _call_with_width(st.dataframe, data, *args, width=width, **kwargs)


def _call_with_width(
    method: Callable[..., ReturnType],
    /,
    *args: Any,
    width: WidthMode,
    **kwargs: Any,
) -> ReturnType:
    try:
        return method(*args, width=width, **kwargs)
    except TypeError as exc:
        if not _is_width_compat_error(exc):
            raise
        return method(*args, use_container_width=width == "stretch", **kwargs)


def _is_width_compat_error(exc: TypeError) -> bool:
    message = str(exc)
    return (
        "unexpected keyword argument 'width'" in message
        or "'str' object cannot be interpreted as an integer" in message
    )
