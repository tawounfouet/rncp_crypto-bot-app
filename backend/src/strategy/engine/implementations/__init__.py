"""
Strategy implementations package for the Crypto Trading Bot.
"""

from .moving_average_crossover import MovingAverageCrossoverStrategy
from .rsi_reversal import RSIReversalStrategy
from .bollinger_bands import BollingerBandsStrategy
from .multi_indicator import MultiIndicatorStrategy

__all__ = [
    "MovingAverageCrossoverStrategy",
    "RSIReversalStrategy",
    "BollingerBandsStrategy",
    "MultiIndicatorStrategy",
]
