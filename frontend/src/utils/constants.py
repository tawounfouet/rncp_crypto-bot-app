"""Constantes transverses du frontend Streamlit."""

from __future__ import annotations

APP_NAME = "Crypto Bot Spot - MVP Frontend"

DEFAULT_PASSWORD_MIN_LENGTH = 8

ACTION_START = "start"
ACTION_PAUSE = "pause"
ACTION_STOP = "stop"

EXCHANGE_SETUP_CTA_LABEL = "Configurer mes clés d'exchange"
ACCOUNT_SETTINGS_PAGE_PATH = "pages/07_Gestion_de_compte.py"

# Catalogue des exchanges proposables dans l'UI (cf. issue #13 — sortie Binance MiCA).
# Alignes sur utils/connectors/exchanges/ccxt_driver.py:CCXT_IDS cote backend.
EXCHANGE_CATALOG: dict[str, str] = {
    "binance": "Binance",
    "kraken": "Kraken",
}
DEFAULT_EXCHANGE = "binance"
