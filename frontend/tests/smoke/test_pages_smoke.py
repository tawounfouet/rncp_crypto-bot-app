from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest

from mocks.db import create_mock_store
from utils.constants import EXCHANGE_SETUP_CTA_LABEL


SRC_DIR = Path(__file__).resolve().parents[2] / "src"


_SMOKE_TOKEN = "smoke-test-token"


def _run_app(
    relative_path: str,
    auth_email: str | None = None,
    *,
    exchange_configured: bool | None = None,
    custom_store=None,
) -> AppTest:
    at = AppTest.from_file(str(SRC_DIR / relative_path))
    if custom_store is not None:
        at.session_state["app_store"] = custom_store
        # Injecte un token factice pour que les services puissent appeler le backend stub
        at.session_state["access_token"] = _SMOKE_TOKEN
        at.run(timeout=20)
        return at
    if auth_email:
        store = create_mock_store(disable_latency=True)
        store.current_user_email = auth_email
        if exchange_configured is not None and auth_email in store.users:
            store.users[auth_email].exchange_configured = exchange_configured
            if not exchange_configured:
                store.exchange_credentials.pop(auth_email, None)
                store.credential_updated_at.pop(auth_email, None)
            elif auth_email not in store.exchange_credentials:
                store.exchange_credentials[auth_email] = ("AK_RESTORED_1234", "AS_RESTORED_9876")
                store.credential_updated_at[auth_email] = datetime.now(UTC)
        at.session_state["app_store"] = store
        # Injecte un token factice pour que les services puissent appeler le backend stub
        at.session_state["access_token"] = _SMOKE_TOKEN
    at.run(timeout=20)
    return at


def _assert_no_exception(at: AppTest) -> None:
    assert len(at.exception) == 0


def _sidebar_captions(at: AppTest) -> list[str]:
    return [caption.value for caption in at.sidebar.caption]


@pytest.mark.parametrize(
    "relative_path",
    [
        "app.py",
        "pages/01_Marche.py",
        "pages/02_Inscription.py",
    ],
)
def test_public_pages_render(relative_path: str) -> None:
    at = _run_app(relative_path)
    _assert_no_exception(at)


def test_market_page_renders_for_anonymous_user() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    assert any(selectbox.label == "Plateforme" for selectbox in at.selectbox)
    metric_labels = [metric.label for metric in at.metric]
    assert "BTCUSDT" in metric_labels
    assert "ETHUSDT" in metric_labels


def test_market_page_has_no_error_or_warning_banner_for_anonymous_user() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    assert len(at.error) == 0
    assert len(at.warning) == 0
    orange_captions = [caption.value for caption in at.caption if ":orange[" in caption.value]
    assert orange_captions == []


def test_market_page_has_no_error_or_warning_banner_for_authenticated_user() -> None:
    at = _run_app("pages/01_Marche.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    assert len(at.error) == 0
    assert len(at.warning) == 0
    orange_captions = [caption.value for caption in at.caption if ":orange[" in caption.value]
    assert orange_captions == []


def test_market_page_renders_one_candlestick_chart_per_pair() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    subheaders = [subheader.value for subheader in at.subheader]
    assert "BTCUSDT" in subheaders
    assert "ETHUSDT" in subheaders
    assert any(radio.label == "Période" for radio in at.radio)
    charts = at.get("plotly_chart")
    assert len(charts) == 2
    chart_titles = [json.loads(chart.proto.spec)["layout"]["title"]["text"] for chart in charts]
    assert chart_titles == ["Binance", "Binance"]  # nom de la plateforme dans le titre de chaque graphique


def test_market_page_compare_mode_defaults_to_none() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    compare_select = next(sb for sb in at.selectbox if sb.label == "Comparer avec")
    assert compare_select.value == "__none__"


def test_market_page_compare_mode_shows_charts_for_both_platforms() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    compare_select = next(sb for sb in at.selectbox if sb.label == "Comparer avec")

    at = compare_select.set_value("kraken").run(timeout=20)
    _assert_no_exception(at)
    charts = at.get("plotly_chart")
    assert len(charts) == 4  # 2 paires x 2 plateformes
    chart_titles = [json.loads(chart.proto.spec)["layout"]["title"]["text"] for chart in charts]
    assert chart_titles.count("Binance") == 2
    assert chart_titles.count("Kraken") == 2
    # une seule periode partagee par paire en mode comparaison, pas une par plateforme
    assert sum(1 for radio in at.radio if radio.label == "Période") == 2


def test_market_page_compare_mode_has_no_error_or_warning_banner() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    compare_select = next(sb for sb in at.selectbox if sb.label == "Comparer avec")

    at = compare_select.set_value("kraken").run(timeout=20)
    _assert_no_exception(at)
    assert len(at.error) == 0
    assert len(at.warning) == 0


def test_market_page_timeframe_choice_is_independent_per_pair() -> None:
    at = _run_app("pages/01_Marche.py")
    _assert_no_exception(at)
    btc_radio = next(r for r in at.radio if r.key == "timeframe_BTCUSDT")
    eth_radio_before = next(r for r in at.radio if r.key == "timeframe_ETHUSDT").value

    at = btc_radio.set_value("Dernier jour").run(timeout=20)
    _assert_no_exception(at)
    eth_radio_after = next(r for r in at.radio if r.key == "timeframe_ETHUSDT").value
    assert eth_radio_after == eth_radio_before


def test_market_page_renders_for_authenticated_user() -> None:
    at = _run_app("pages/01_Marche.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    assert any(selectbox.label == "Plateforme" for selectbox in at.selectbox)


def test_market_page_listed_in_anonymous_sidebar() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py")
    _assert_no_exception(at)
    captions = _sidebar_captions(at)
    assert "Marché" in captions


def test_market_page_listed_in_authenticated_sidebar() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    captions = _sidebar_captions(at)
    assert "Marché" in captions


@pytest.mark.parametrize(
    "relative_path",
    [
        "pages/03_Portefeuille_Spot.py",
        "pages/04_Performances_Spot.py",
        "pages/05_Controle_Bot_Spot.py",
        "pages/06_Parametrage_Bot_Spot.py",
        "pages/07_Gestion_de_compte.py",
    ],
)
def test_protected_pages_render_with_user_session(relative_path: str) -> None:
    at = _run_app(relative_path, auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)


def test_admin_page_render_with_admin_session() -> None:
    at = _run_app("pages/08_Admin.py", auth_email="admin@cryptobot.dev")
    _assert_no_exception(at)


def test_sidebar_rules_for_anonymous_user_on_protected_page() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py")
    _assert_no_exception(at)
    captions = _sidebar_captions(at)
    assert "Connexion" in captions
    assert "Inscription" in captions
    assert "Admin" not in captions
    assert "Portefeuille Spot" not in captions


def test_sidebar_rules_for_standard_user() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    captions = _sidebar_captions(at)
    assert "Inscription" not in captions
    assert "Admin" not in captions
    assert "Portefeuille Spot" in captions


def test_sidebar_rules_for_admin_user() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py", auth_email="admin@cryptobot.dev")
    _assert_no_exception(at)
    captions = _sidebar_captions(at)
    assert "Admin" in captions


def test_admin_page_access_denied_for_standard_user() -> None:
    at = _run_app("pages/08_Admin.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    assert len(at.error) == 1
    assert "administrateurs" in at.error[0].value


def test_navigation_header_rendered_once() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    headers = [entry.value for entry in at.sidebar.markdown if "### Navigation" in entry.value]
    assert len(headers) == 1


@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("app.py", None),
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
    ],
)
def test_theme_switch_visible_in_sidebar(relative_path: str, auth_email: str | None) -> None:
    at = _run_app(relative_path, auth_email=auth_email)
    _assert_no_exception(at)
    assert any(toggle.label == "Mode clair" for toggle in at.sidebar.toggle)


def test_theme_switch_persists_store_mode_across_pages() -> None:
    at = _run_app("pages/03_Portefeuille_Spot.py", auth_email="alice@cryptobot.dev")
    _assert_no_exception(at)
    assert at.session_state["app_store"].ui_theme_mode == "dark"

    theme_toggle = next(toggle for toggle in at.sidebar.toggle if toggle.label == "Mode clair")
    at = theme_toggle.set_value(True).run(timeout=20)
    _assert_no_exception(at)
    assert at.session_state["app_store"].ui_theme_mode == "light"

    shared_store = at.session_state["app_store"]
    next_page = _run_app("pages/04_Performances_Spot.py", custom_store=shared_store)
    _assert_no_exception(next_page)
    assert next_page.session_state["app_store"].ui_theme_mode == "light"


@pytest.mark.parametrize("theme_mode", ["light", "dark"])
@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
        ("pages/04_Performances_Spot.py", "alice@cryptobot.dev"),
        ("pages/06_Parametrage_Bot_Spot.py", "alice@cryptobot.dev"),
        ("pages/08_Admin.py", "admin@cryptobot.dev"),
    ],
)
def test_select_pages_render_select_widgets_in_both_themes(
    relative_path: str,
    auth_email: str,
    theme_mode: str,
) -> None:
    store = create_mock_store(disable_latency=True)
    store.current_user_email = auth_email
    store.ui_theme_mode = theme_mode

    at = _run_app(relative_path, custom_store=store)
    _assert_no_exception(at)
    assert len(at.selectbox) >= 1


@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("app.py", None),
        ("pages/02_Inscription.py", None),
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
        ("pages/04_Performances_Spot.py", "alice@cryptobot.dev"),
        ("pages/05_Controle_Bot_Spot.py", "alice@cryptobot.dev"),
        ("pages/06_Parametrage_Bot_Spot.py", "alice@cryptobot.dev"),
        ("pages/07_Gestion_de_compte.py", "alice@cryptobot.dev"),
        ("pages/08_Admin.py", "admin@cryptobot.dev"),
    ],
)
def test_pages_render_in_light_theme(relative_path: str, auth_email: str | None) -> None:
    store = create_mock_store(disable_latency=True)
    store.ui_theme_mode = "light"
    if auth_email:
        store.current_user_email = auth_email

    at = _run_app(relative_path, custom_store=store)
    _assert_no_exception(at)
    assert at.session_state["app_store"].ui_theme_mode == "light"


@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("app.py", None),
        ("pages/02_Inscription.py", None),
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
        ("pages/04_Performances_Spot.py", "alice@cryptobot.dev"),
        ("pages/05_Controle_Bot_Spot.py", "alice@cryptobot.dev"),
        ("pages/06_Parametrage_Bot_Spot.py", "alice@cryptobot.dev"),
        ("pages/07_Gestion_de_compte.py", "alice@cryptobot.dev"),
        ("pages/08_Admin.py", "admin@cryptobot.dev"),
    ],
)
def test_pages_render_in_dark_theme(relative_path: str, auth_email: str | None) -> None:
    store = create_mock_store(disable_latency=True)
    store.ui_theme_mode = "dark"
    if auth_email:
        store.current_user_email = auth_email

    at = _run_app(relative_path, custom_store=store)
    _assert_no_exception(at)
    assert at.session_state["app_store"].ui_theme_mode == "dark"


@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
        ("pages/04_Performances_Spot.py", "alice@cryptobot.dev"),
        ("pages/08_Admin.py", "admin@cryptobot.dev"),
    ],
)
def test_light_theme_tables_use_custom_light_table_renderer(
    relative_path: str,
    auth_email: str,
) -> None:
    store = create_mock_store(disable_latency=True)
    store.ui_theme_mode = "light"
    store.current_user_email = auth_email

    at = _run_app(relative_path, custom_store=store)
    _assert_no_exception(at)
    markdown_payload = " ".join(entry.value for entry in at.markdown)
    assert "theme-table-wrapper" in markdown_payload


def test_portfolio_shows_exchange_prerequisite_without_kpis_when_not_configured() -> None:
    at = _run_app(
        "pages/03_Portefeuille_Spot.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=False,
    )
    _assert_no_exception(at)
    markdown_values = [entry.value for entry in at.markdown]
    assert any("Pré-requis exchange manquant" in value for value in markdown_values)
    assert not any("Valeur totale" in value for value in markdown_values)
    assert EXCHANGE_SETUP_CTA_LABEL in [button.label for button in at.button]


def test_performance_shows_exchange_prerequisite_without_performance_content_when_not_configured() -> None:
    at = _run_app(
        "pages/04_Performances_Spot.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=False,
    )
    _assert_no_exception(at)
    markdown_values = [entry.value for entry in at.markdown]
    assert any("Pré-requis exchange manquant" in value for value in markdown_values)
    assert not any("PnL realise" in value for value in markdown_values)
    assert not any("Equity curve" in value for value in markdown_values)
    assert EXCHANGE_SETUP_CTA_LABEL in [button.label for button in at.button]


def test_bot_control_shows_only_bot_list_when_exchange_not_configured() -> None:
    at = _run_app(
        "pages/05_Controle_Bot_Spot.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=False,
    )
    _assert_no_exception(at)
    assert "Bots Spot disponibles" in [subheader.value for subheader in at.subheader]
    assert not any(button.label in {"Start", "Pause", "Stop"} for button in at.button)
    page_markdown = " ".join(entry.value for entry in at.markdown)
    for token in ["RUNNING", "STOPPED", "PAUSED", "ERROR", "Statut:"]:
        assert token not in page_markdown
    assert EXCHANGE_SETUP_CTA_LABEL in [button.label for button in at.button]


def test_bot_config_hides_runtime_metadata_when_exchange_not_configured() -> None:
    at = _run_app(
        "pages/06_Parametrage_Bot_Spot.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=False,
    )
    _assert_no_exception(at)
    assert "Bots Spot disponibles" in [subheader.value for subheader in at.subheader]
    assert not any(selectbox.label == "Bot selectionne" for selectbox in at.selectbox)
    assert not any(metric.label == "Version config" for metric in at.metric)
    assert not any(metric.label == "Date modif" for metric in at.metric)
    assert not any(button.label in {"Valider", "Sauvegarder"} for button in at.button)
    markdown_values = " ".join(entry.value for entry in at.markdown)
    assert "Statut actuel" not in markdown_values
    assert EXCHANGE_SETUP_CTA_LABEL in [button.label for button in at.button]


def test_account_prioritizes_exchange_setup_when_not_configured() -> None:
    at = _run_app(
        "pages/07_Gestion_de_compte.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=False,
    )
    _assert_no_exception(at)
    markdown_values = [entry.value for entry in at.markdown]
    assert any("prioritaire" in value.lower() for value in markdown_values)


def test_admin_page_shows_exchange_configured_indicator_column() -> None:
    at = _run_app("pages/08_Admin.py", auth_email="admin@cryptobot.dev")
    _assert_no_exception(at)
    assert at.dataframe
    frame = at.dataframe[0].value
    exchange_columns = [column for column in frame.columns if "Exchange" in str(column)]
    assert exchange_columns
    values = set(frame[exchange_columns[0]].tolist())
    assert values.issubset({"Oui", "Non"})


@pytest.mark.parametrize(
    ("relative_path", "auth_email"),
    [
        ("pages/03_Portefeuille_Spot.py", "alice@cryptobot.dev"),
        ("pages/04_Performances_Spot.py", "alice@cryptobot.dev"),
        ("pages/08_Admin.py", "admin@cryptobot.dev"),
    ],
)
def test_table_dataframes_do_not_expose_internal_technical_metadata(
    relative_path: str,
    auth_email: str,
) -> None:
    at = _run_app(relative_path, auth_email=auth_email)
    _assert_no_exception(at)
    assert at.dataframe
    for dataframe in at.dataframe:
        assert "__field_validators__" not in dataframe.value.columns


def test_account_page_does_not_show_priority_banner_when_exchange_configured() -> None:
    # alice est configuree sur son exchange par defaut (binance) dans le mock store
    at = _run_app(
        "pages/07_Gestion_de_compte.py",
        auth_email="alice@cryptobot.dev",
        exchange_configured=True,
    )
    _assert_no_exception(at)
    page_markdown = " ".join(entry.value for entry in at.markdown).lower()
    assert "prioritaire: configurer" not in page_markdown
    assert "binance: enabled" in page_markdown
