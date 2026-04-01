"""
Strategy registry system for the Crypto Trading Bot.
Manages registration, discovery, and instantiation of trading strategies.
"""

import importlib
import logging
import pkgutil
from typing import Any

from .base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Central registry for managing trading strategies.

    This class handles strategy registration, discovery, and instantiation.
    It supports both automatic discovery of strategies and manual registration.
    """

    def __init__(self):
        self._strategies: dict[str, type[BaseStrategy]] = {}
        self._strategy_metadata: dict[str, dict[str, Any]] = {}

    def register(
        self,
        name: str,
        strategy_class: type[BaseStrategy],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a strategy class.

        Args:
            name: Strategy identifier
            strategy_class: Strategy class that inherits from BaseStrategy
            metadata: Optional metadata about the strategy

        Raises:
            ValueError: If strategy name already exists or class is invalid
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"Strategy class {strategy_class} must inherit from BaseStrategy")

        if name in self._strategies:
            logger.warning(f"Strategy '{name}' already registered, overwriting")

        self._strategies[name] = strategy_class
        self._strategy_metadata[name] = metadata or {}

        logger.info(f"Registered strategy: {name}")

    def unregister(self, name: str) -> None:
        """
        Unregister a strategy.

        Args:
            name: Strategy identifier to remove
        """
        if name in self._strategies:
            del self._strategies[name]
            if name in self._strategy_metadata:
                del self._strategy_metadata[name]
            logger.info(f"Unregistered strategy: {name}")
        else:
            logger.warning(f"Strategy '{name}' not found for unregistration")

    def get_strategy_class(self, name: str) -> type[BaseStrategy]:
        """
        Get a strategy class by name.

        Args:
            name: Strategy identifier

        Returns:
            Strategy class

        Raises:
            KeyError: If strategy not found
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found in registry")

        return self._strategies[name]

    def create_strategy(self, name: str, params: dict[str, Any] | None = None) -> BaseStrategy:
        """
        Create a strategy instance.

        Args:
            name: Strategy identifier
            params: Strategy parameters

        Returns:
            Strategy instance

        Raises:
            KeyError: If strategy not found
            Exception: If strategy instantiation fails
        """
        try:
            strategy_class = self.get_strategy_class(name)
            return strategy_class(name=name, params=params)
        except Exception as e:
            logger.error(f"Failed to create strategy '{name}': {e!s}")
            raise

    def list_strategies(self) -> list[str]:
        """
        Get list of all registered strategy names.

        Returns:
            List of strategy names
        """
        return list(self._strategies.keys())

    def get_strategy_info(self, name: str) -> dict[str, Any]:
        """
        Get information about a strategy.

        Args:
            name: Strategy identifier

        Returns:
            Dictionary with strategy information

        Raises:
            KeyError: If strategy not found
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' not found in registry")

        strategy_class = self._strategies[name]
        metadata = self._strategy_metadata[name]

        return {
            "name": name,
            "class": strategy_class.__name__,
            "module": strategy_class.__module__,
            "docstring": strategy_class.__doc__,
            "metadata": metadata,
        }

    def get_all_strategies_info(self) -> dict[str, dict[str, Any]]:
        """
        Get information about all registered strategies.

        Returns:
            Dictionary mapping strategy names to their information
        """
        return {name: self.get_strategy_info(name) for name in self.list_strategies()}

    def discover_strategies(self, package_path: str = "src.backend.strategies.implementations") -> int:
        """
        Automatically discover and register strategies from a package.

        Args:
            package_path: Python package path to search for strategies

        Returns:
            Number of strategies discovered and registered
        """
        discovered_count = 0

        try:
            # Import the package
            package = importlib.import_module(package_path)

            # Get package directory
            if hasattr(package, "__path__"):
                package_dir = package.__path__[0]
            else:
                logger.warning(f"Package {package_path} has no __path__ attribute")
                return 0

            # Walk through all modules in the package
            for _importer, modname, ispkg in pkgutil.walk_packages([package_dir]):
                if ispkg:
                    continue

                try:
                    # Import the module
                    full_module_name = f"{package_path}.{modname}"
                    module = importlib.import_module(full_module_name)

                    # Look for strategy classes
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)

                        # Check if it's a strategy class
                        if isinstance(attr, type) and issubclass(attr, BaseStrategy) and attr != BaseStrategy:
                            # Register the strategy
                            strategy_name = getattr(attr, "STRATEGY_NAME", attr.__name__.lower())
                            self.register(strategy_name, attr)
                            discovered_count += 1

                except ImportError as e:
                    logger.warning(f"Could not import module {modname}: {e!s}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing module {modname}: {e!s}")
                    continue

        except ImportError as e:
            logger.error(f"Could not import package {package_path}: {e!s}")

        logger.info(f"Discovered and registered {discovered_count} strategies")
        return discovered_count

    def validate_strategy(self, name: str, params: dict[str, Any] | None = None) -> tuple[bool, str | None]:
        """
        Validate a strategy and its parameters.

        Args:
            name: Strategy identifier
            params: Strategy parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if strategy exists
            if name not in self._strategies:
                return False, f"Strategy '{name}' not found in registry"

            # Try to create an instance with the parameters
            strategy = self.create_strategy(name, params)

            # Validate parameters if the strategy supports it
            if hasattr(strategy, "validate_parameters"):
                return strategy.validate_parameters()

            return True, None

        except Exception as e:
            return False, f"Strategy validation failed: {e!s}"

    def clear(self) -> None:
        """Clear all registered strategies."""
        self._strategies.clear()
        self._strategy_metadata.clear()
        logger.info("Cleared all registered strategies")


# Global registry instance
registry = StrategyRegistry()


def register_strategy(name: str, metadata: dict[str, Any] | None = None):
    """
    Decorator for registering strategy classes.

    Args:
        name: Strategy identifier
        metadata: Optional metadata about the strategy
    """

    def decorator(strategy_class: type[BaseStrategy]):
        registry.register(name, strategy_class, metadata)
        return strategy_class

    return decorator


def get_strategy(name: str, params: dict[str, Any] | None = None) -> BaseStrategy:
    """
    Convenience function to create a strategy instance.

    Args:
        name: Strategy identifier
        params: Strategy parameters

    Returns:
        Strategy instance
    """
    return registry.create_strategy(name, params)


def list_available_strategies() -> list[str]:
    """
    Get list of all available strategies.

    Returns:
        List of strategy names
    """
    return registry.list_strategies()


def get_strategy_info(name: str) -> dict[str, Any]:
    """
    Get information about a specific strategy.

    Args:
        name: Strategy identifier

    Returns:
        Dictionary with strategy information
    """
    return registry.get_strategy_info(name)
