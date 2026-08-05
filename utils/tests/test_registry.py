from __future__ import annotations

import pytest

from utils.connectors.exchanges.registry import get_market_data_driver
from utils.connectors.exchanges.binance_native import BinanceMarketDataDriver

def test_get_market_data_driver_returns_native_for_registered_exchange():


    driver = get_market_data_driver("binance")
    assert isinstance(driver, BinanceMarketDataDriver)

    driver = get_market_data_driver("BINANCE")
    assert isinstance(driver, BinanceMarketDataDriver)

    driver = get_market_data_driver("Kraken")
    assert driver.source == "kraken"
