from __future__ import annotations

from services.bot_config_service import BotConfigService


def test_bot_catalog_lists_locked_templates(store) -> None:
    service = BotConfigService(store)
    templates = service.list_templates()

    assert templates
    template = templates[0]
    assert template.symbol
    assert template.timeframe
    assert template.execution_params
    assert template.risk_limits
    assert template.order_policy


def test_select_template_creates_locked_user_selection(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotConfigService(store)
    template = service.list_templates()[0]

    ok, message, selection = service.select_template(template.id)

    assert ok is True
    assert "verrouillee" in message
    assert selection is not None
    assert selection.template_id == template.id
    assert selection.config_snapshot["symbol"] == template.symbol
    assert selection.config_snapshot["timeframe"] == template.timeframe
    assert selection.config_snapshot["risk_limits"] == template.risk_limits


def test_select_template_rejects_duplicate_selection(store) -> None:
    store.current_user_email = "alice@cryptobot.dev"
    service = BotConfigService(store)
    template = service.list_templates()[0]

    first_ok, _, _ = service.select_template(template.id)
    second_ok, second_message, second_selection = service.select_template(template.id)

    assert first_ok is True
    assert second_ok is False
    assert "deja selectionne" in second_message
    assert second_selection is None
