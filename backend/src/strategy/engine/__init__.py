"""
Strategies package for the Crypto Trading Bot.
Contains the strategy engine, indicators, and strategy implementations.
"""

from .base_strategy import BaseStrategy

# Import all strategy implementations to register them
from .implementations import (
    BollingerBandsStrategy,
    MovingAverageCrossoverStrategy,
    MultiIndicatorStrategy,
    RSIReversalStrategy,
)
from .indicators import TechnicalIndicators
from .registry import (
    get_strategy,
    get_strategy_info,
    list_available_strategies,
    register_strategy,
    registry,
)

# Auto-discover and register strategies
registry.discover_strategies("src.backend.strategies.implementations")

__all__ = [
    "BaseStrategy",
    "BollingerBandsStrategy",
    "MovingAverageCrossoverStrategy",
    "MultiIndicatorStrategy",
    "RSIReversalStrategy",
    "TechnicalIndicators",
    "get_strategy",
    "get_strategy_info",
    "list_available_strategies",
    "register_strategy",
    "registry",
]
