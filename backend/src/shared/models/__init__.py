"""
Shared models package.
Contains the base model classes and a lazy ALL_MODELS registry.

Domain models are imported lazily (via functions) to avoid circular imports,
since domain model files import from shared.models.base.
"""

from .base import (
    Base,
    BaseModel,
    BaseModelWithSoftDelete,
    BaseAuditModel,
    BaseFullAuditModel,
    UUIDMixin,
    TimestampMixin,
    SoftDeleteMixin,
    AuditMixin,
    ModelRegistry,
    register_model,
    get_or_create,
    bulk_create_or_update,
)

__all__ = [
    # Base classes
    "Base",
    "BaseModel",
    "BaseModelWithSoftDelete",
    "BaseAuditModel",
    "BaseFullAuditModel",
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "ModelRegistry",
    "register_model",
    "get_or_create",
    "bulk_create_or_update",
    # Registry functions
    "get_all_models",
    "get_models_by_domain",
    "get_model_by_table_name",
    "create_all_tables",
    "drop_all_tables",
    "validate_model_relationships",
]


def _import_domain_models():
    """Lazily import all domain models to avoid circular imports."""
    from auth.models import User, UserSession, UserAccount, UserSettings
    from strategy.models import (
        Strategy,
        StrategyDeployment,
        StrategyState,
        TradingSession,
        BacktestResult,
    )
    from trading.models import Order, OrderFill, Transaction
    from market.models import MarketData

    return {
        "all": [
            User,
            UserSession,
            UserAccount,
            UserSettings,
            Strategy,
            StrategyDeployment,
            StrategyState,
            TradingSession,
            BacktestResult,
            Order,
            OrderFill,
            Transaction,
            MarketData,
        ],
        "user": [User, UserSession, UserAccount, UserSettings],
        "strategy": [
            Strategy,
            StrategyDeployment,
            StrategyState,
            TradingSession,
            BacktestResult,
        ],
        "trading": [Order, OrderFill, Transaction],
        "market": [MarketData],
    }


def get_all_models() -> list:
    """Get all registered domain models."""
    return _import_domain_models()["all"]


# Keep ALL_MODELS as a lazy property for backward compatibility
class _LazyAllModels:
    """Descriptor that lazily loads ALL_MODELS on first access."""

    def __init__(self):
        self._models = None

    def __iter__(self):
        if self._models is None:
            self._models = get_all_models()
        return iter(self._models)

    def __len__(self):
        if self._models is None:
            self._models = get_all_models()
        return len(self._models)

    def __getitem__(self, index):
        if self._models is None:
            self._models = get_all_models()
        return self._models[index]


ALL_MODELS = _LazyAllModels()


def get_models_by_domain(domain: str) -> list:
    """Get models by domain name ('user', 'strategy', 'trading', 'market')."""
    return _import_domain_models().get(domain, [])


def get_model_by_table_name(table_name: str):
    """Get model class by table name."""
    for model in get_all_models():
        if hasattr(model, "__tablename__") and model.__tablename__ == table_name:
            return model
    return None


def create_all_tables(engine):
    """Create all tables in the database."""
    Base.metadata.create_all(bind=engine)


def drop_all_tables(engine):
    """Drop all tables in the database."""
    Base.metadata.drop_all(bind=engine)


def validate_model_relationships():
    """Validate that all model relationships are properly defined."""
    try:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite:///:memory:")
        create_all_tables(engine)
        return True
    except Exception as e:
        print(f"Model validation error: {e}")
        return False
