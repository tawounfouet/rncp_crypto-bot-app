"""Tests unitaires pour utils.trading.signals."""

from utils.trading.signals import SIGNAL_TO_VALUE, VALUE_TO_SIGNAL


def test_signal_to_value_and_back_are_consistent():
    for label, value in SIGNAL_TO_VALUE.items():
        assert VALUE_TO_SIGNAL[value] == label


def test_expected_signal_labels():
    assert SIGNAL_TO_VALUE == {"BUY": 1, "HOLD": 0, "SELL": -1}
