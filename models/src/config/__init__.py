"""Configuration package for models-training."""

from src.config.config_loader import load_config
from src.config.settings import AppSettings

__all__ = ["AppSettings", "load_config"]
