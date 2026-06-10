"""Project-specific exceptions."""


class ModelsTrainingError(Exception):
    """Base exception for models-training errors."""


class MissingDependencyError(ModelsTrainingError):
    """Raised when an optional runtime dependency is not installed."""


class ConfigurationError(ModelsTrainingError):
    """Raised when the project configuration is invalid."""


class DataValidationError(ModelsTrainingError):
    """Raised when market data validation fails."""
