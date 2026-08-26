from __future__ import annotations

from prerequisites.exchange import (
    ExchangeRequirementMode,
    evaluate_exchange_prerequisite,
    missing_copy_for_page,
    page_requires_exchange,
    requirement_mode_for_page,
)


def test_requirement_mode_by_page() -> None:
    assert requirement_mode_for_page("dashboard") == ExchangeRequirementMode.BLOCK_CONTENT
    assert requirement_mode_for_page("portfolio") == ExchangeRequirementMode.BLOCK_CONTENT
    assert requirement_mode_for_page("performance") == ExchangeRequirementMode.BLOCK_CONTENT
    assert requirement_mode_for_page("bot_control") == ExchangeRequirementMode.DISABLE_ACTIONS
    assert requirement_mode_for_page("bot_config") == ExchangeRequirementMode.READ_ONLY
    assert requirement_mode_for_page("account") == ExchangeRequirementMode.NONE


def test_page_requires_exchange_flag() -> None:
    assert page_requires_exchange("dashboard") is True
    assert page_requires_exchange("portfolio") is True
    assert page_requires_exchange("account") is False


def test_portfolio_is_blocked_when_exchange_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.exchange_configured = False
    status = evaluate_exchange_prerequisite("portfolio", user)
    assert status.missing is True
    assert status.should_block_content is True
    assert status.actions_disabled is False


def test_bot_control_disables_actions_when_exchange_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.exchange_configured = False
    status = evaluate_exchange_prerequisite("bot_control", user)
    assert status.missing is True
    assert status.should_block_content is False
    assert status.actions_disabled is True
    assert status.read_only is False


def test_bot_config_read_only_when_exchange_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.exchange_configured = False
    status = evaluate_exchange_prerequisite("bot_config", user)
    assert status.missing is True
    assert status.actions_disabled is True
    assert status.read_only is True


def test_no_exchange_gate_for_anonymous_user() -> None:
    status = evaluate_exchange_prerequisite("portfolio", None)
    assert status.missing is False
    assert status.should_block_content is False


def test_no_exchange_gate_when_user_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.exchange_configured = True
    status = evaluate_exchange_prerequisite("portfolio", user)
    assert status.missing is False
    assert status.should_block_content is False


def test_missing_copy_is_defined_for_supported_pages() -> None:
    title, message = missing_copy_for_page("portfolio")
    assert "exchange" in title.lower()
    assert "portefeuille" in message.lower()
