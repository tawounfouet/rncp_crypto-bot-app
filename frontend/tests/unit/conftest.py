from __future__ import annotations

import pytest
import streamlit as st

from mocks.db import MockStore, create_mock_store


@pytest.fixture(autouse=True)
def clean_streamlit_session():
    st.session_state.clear()
    yield
    st.session_state.clear()


@pytest.fixture
def store() -> MockStore:
    return create_mock_store(disable_latency=True)
