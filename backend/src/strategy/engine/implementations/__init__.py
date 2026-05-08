"""
Strategy implementations package for the Crypto Trading Bot.
"""

from .bollinger_bands import BollingerBandsStrategy
from .moving_average_crossover import MovingAverageCrossoverStrategy
from .multi_indicator import MultiIndicatorStrategy
from .rsi_reversal import RSIReversalStrategy

__all__ = [
    "BollingerBandsStrategy",
    "MovingAverageCrossoverStrategy",
    "MultiIndicatorStrategy",
    "RSIReversalStrategy",
]
