"""Inventory schemas (spec.md §5.5)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, computed_field

from app.schemas.common import ORMModel
from app.units import Dimension, from_base

# `>= 0` (an inventory quantity may legitimately be zero) and finite. Declared as
# `Annotated[...]` so the constraint lands on the value, not on a nullable union.
NonNegativeQuantity = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class InventoryItemCreate(BaseModel):
    """`POST /api/inventory` body — additive upsert.

    `match_name` (supplied or derived from `item`) is `normalize_name`d before
    store by the router; a value that normalizes to `""` is a 422 (N5).
    """

    item: Annotated[str, Field(min_length=1, max_length=200)]
    quantity: NonNegativeQuantity
    unit: Annotated[str, Field(max_length=30)] | None = None
    match_name: Annotated[str, Field(max_length=200)] | None = None


class InventoryItemUpdate(BaseModel):
    """`PATCH /api/inventory/{id}` body — absolute replacement, driven by
    `model_fields_set`: an absent field is untouched, a present-and-null `item` /
    `match_name` / `quantity` is a 422 (the router enforces this)."""

    item: Annotated[str, Field(max_length=200)] | None = None
    match_name: Annotated[str, Field(max_length=200)] | None = None
    quantity: NonNegativeQuantity | None = None
    unit: Annotated[str, Field(max_length=30)] | None = None


class InventoryItemRead(ORMModel):
    id: int
    item: str
    normalized_name: str
    match_name: str
    unit_bucket: str
    quantity_base: float
    display_unit: str | None
    updated_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def display_quantity(self) -> float:
        """`from_base(quantity_base, dim, display_unit)`, falling back to
        `quantity_base` when there is no preference, the bucket is opaque, or the
        unit does not convert (spec.md §5.5)."""
        if self.display_unit is None or self.unit_bucket.startswith("opaque:"):
            return self.quantity_base
        try:
            dim = Dimension(self.unit_bucket)
        except ValueError:
            return self.quantity_base
        converted = from_base(self.quantity_base, dim, self.display_unit)
        return self.quantity_base if converted is None else converted
