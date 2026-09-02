"""Shared schema utilities."""

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base model for ORM object serialization."""

    model_config = ConfigDict(from_attributes=True)
