from __future__ import annotations

from prerequisites.binance import (
    BinanceRequirementMode,
    evaluate_binance_prerequisite,
    missing_copy_for_page,
    page_requires_binance,
    requirement_mode_for_page,
)


def test_requirement_mode_by_page() -> None:
    assert requirement_mode_for_page("portfolio") == BinanceRequirementMode.BLOCK_CONTENT
    assert requirement_mode_for_page("performance") == BinanceRequirementMode.BLOCK_CONTENT
    assert requirement_mode_for_page("bot_control") == BinanceRequirementMode.DISABLE_ACTIONS
    assert requirement_mode_for_page("bot_config") == BinanceRequirementMode.READ_ONLY
    assert requirement_mode_for_page("account") == BinanceRequirementMode.NONE


def test_page_requires_binance_flag() -> None:
    assert page_requires_binance("portfolio") is True
    assert page_requires_binance("account") is False


def test_portfolio_is_blocked_when_binance_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.binance_configured = False
    status = evaluate_binance_prerequisite("portfolio", user)
    assert status.missing is True
    assert status.should_block_content is True
    assert status.actions_disabled is False


def test_bot_control_disables_actions_when_binance_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.binance_configured = False
    status = evaluate_binance_prerequisite("bot_control", user)
    assert status.missing is True
    assert status.should_block_content is False
    assert status.actions_disabled is True
    assert status.read_only is False


def test_bot_config_read_only_when_binance_not_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.binance_configured = False
    status = evaluate_binance_prerequisite("bot_config", user)
    assert status.missing is True
    assert status.actions_disabled is True
    assert status.read_only is True


def test_no_binance_gate_for_anonymous_user() -> None:
    status = evaluate_binance_prerequisite("portfolio", None)
    assert status.missing is False
    assert status.should_block_content is False


def test_no_binance_gate_when_user_configured(store) -> None:
    user = store.users["alice@cryptobot.dev"]
    user.binance_configured = True
    status = evaluate_binance_prerequisite("portfolio", user)
    assert status.missing is False
    assert status.should_block_content is False


def test_missing_copy_is_defined_for_supported_pages() -> None:
    title, message = missing_copy_for_page("portfolio")
    assert "Binance" in title
    assert "portefeuille" in message.lower()
