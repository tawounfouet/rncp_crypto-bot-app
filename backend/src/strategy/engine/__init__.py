"""
Strategies package for the Crypto Trading Bot.
Contains the strategy engine, indicators, and strategy implementations.
"""

from .base_strategy import BaseStrategy
from .registry import (
    registry,
    register_strategy,
    get_strategy,
    list_available_strategies,
    get_strategy_info,
)
from .indicators import TechnicalIndicators

# Import all strategy implementations to register them
from .implementations import (
    MovingAverageCrossoverStrategy,
    RSIReversalStrategy,
    BollingerBandsStrategy,
    MultiIndicatorStrategy,
)

# Auto-discover and register strategies
registry.discover_strategies("src.backend.strategies.implementations")

__all__ = [
    "BaseStrategy",
    "TechnicalIndicators",
    "registry",
    "register_strategy",
    "get_strategy",
    "list_available_strategies",
    "get_strategy_info",
    "MovingAverageCrossoverStrategy",
    "RSIReversalStrategy",
    "BollingerBandsStrategy",
    "MultiIndicatorStrategy",
]
