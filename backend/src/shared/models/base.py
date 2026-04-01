"""
Base model and mixins for SQLAlchemy models.
Provides common functionality like UUID primary keys, timestamps, etc.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import declarative_base

# Create the base class for all models
Base = declarative_base()


class UUIDMixin:
    """Mixin for UUID primary key."""

    @declared_attr
    def id(cls):
        return Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=func.current_timestamp(), nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
            nullable=False,
        )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True)

    @declared_attr
    def is_deleted(cls):
        return Column(Boolean, default=False, nullable=False)

    def soft_delete(self):
        """Mark the record as deleted."""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()

    def restore(self):
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin:
    """Mixin for audit fields (created_by, updated_by)."""

    @declared_attr
    def created_by(cls):
        return Column(String(36), nullable=True)

    @declared_attr
    def updated_by(cls):
        return Column(String(36), nullable=True)


class BaseModel(Base, UUIDMixin, TimestampMixin):
    """
    Base model class with common functionality.
    All models should inherit from this class.
    """

    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model instance to dictionary.

        Returns:
            dict: Dictionary representation of the model
        """
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """
        Update model instance from dictionary.

        Args:
            data: Dictionary with field values to update
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation of the model."""
        return f"<{self.__class__.__name__}(id={self.id})>"


class BaseModelWithSoftDelete(BaseModel, SoftDeleteMixin):
    """
    Base model with soft delete functionality.
    Use this for models that should support soft deletion.
    """

    __abstract__ = True


class BaseAuditModel(BaseModel, AuditMixin):
    """
    Base model with audit fields.
    Use this for models that need to track who created/updated records.
    """

    __abstract__ = True


class BaseFullAuditModel(BaseModel, SoftDeleteMixin, AuditMixin):
    """
    Base model with full audit functionality (timestamps, soft delete, audit fields).
    Use this for critical models that need complete audit trail.
    """

    __abstract__ = True


# Utility functions for common model operations
def get_or_create(session, model_class, defaults=None, **kwargs):
    """
    Get an existing instance or create a new one.

    Args:
        session: SQLAlchemy session
        model_class: Model class to query
        defaults: Default values for new instance
        **kwargs: Filter criteria

    Returns:
        tuple: (instance, created_flag)
    """
    instance = session.query(model_class).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = dict((k, v) for k, v in kwargs.items())
        if defaults:
            params.update(defaults)
        instance = model_class(**params)
        session.add(instance)
        return instance, True


def bulk_create_or_update(session, model_class, data_list, unique_fields):
    """
    Bulk create or update records.

    Args:
        session: SQLAlchemy session
        model_class: Model class
        data_list: List of dictionaries with record data
        unique_fields: Fields to use for identifying existing records

    Returns:
        tuple: (created_count, updated_count)
    """
    created_count = 0
    updated_count = 0

    for data in data_list:
        # Extract unique field values
        unique_values = {field: data[field] for field in unique_fields if field in data}

        # Try to find existing record
        existing = session.query(model_class).filter_by(**unique_values).first()

        if existing:
            # Update existing record
            existing.update_from_dict(data)
            updated_count += 1
        else:
            # Create new record
            new_record = model_class(**data)
            session.add(new_record)
            created_count += 1

    return created_count, updated_count


# Model metadata for introspection
class ModelRegistry:
    """Registry to keep track of all models for introspection."""

    _models = {}

    @classmethod
    def register(cls, model_class):
        """Register a model class."""
        cls._models[model_class.__name__] = model_class
        return model_class

    @classmethod
    def get_model(cls, name):
        """Get a model class by name."""
        return cls._models.get(name)

    @classmethod
    def get_all_models(cls):
        """Get all registered models."""
        return cls._models.copy()

    @classmethod
    def get_model_names(cls):
        """Get all model names."""
        return list(cls._models.keys())


def register_model(model_class):
    """Decorator to register a model class."""
    return ModelRegistry.register(model_class)
