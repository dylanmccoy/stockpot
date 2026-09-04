"""Grocery list schemas (spec.md §1 "grocery_lists"/"grocery_list_items", §5.6)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.auth import UserMini
from app.schemas.common import ORMModel

# `> 0` and finite. Declared as `Annotated[...] | None` so the constraint lands
# on the value, not on the nullable union — same convention as the recipe /
# inventory schemas.
PositiveMultiplier = Annotated[float, Field(gt=0, allow_inf_nan=False)]
PositiveAmount = Annotated[float, Field(gt=0, allow_inf_nan=False)]


class GroceryListCreate(BaseModel):
    """`POST /api/grocery` body (spec.md §5.6).

    `recipe_ids` non-empty is enforced here; uniqueness and existence need a DB
    round-trip and are checked by the router. `multipliers` keys ⊆ `recipe_ids`
    is likewise a router-side cross-field check; each value's `> 0` / finite
    bound is enforced here.
    """

    name: Annotated[str, Field(max_length=200)] | None = None
    recipe_ids: Annotated[list[int], Field(min_length=1)]
    multipliers: dict[int, PositiveMultiplier] = {}


class GroceryListItemIn(BaseModel):
    """`POST /api/grocery/{id}/items` body — a manual line (spec.md §5.6).

    Manual amounts are stored exactly as typed, so both keys are required
    (possibly `null`) rather than defaulted — an amount-less manual item still
    sends `quantity: null, unit: null` explicitly.
    """

    item: Annotated[str, Field(min_length=1, max_length=200)]
    quantity: PositiveAmount | None
    unit: Annotated[str, Field(max_length=30)] | None


class GroceryListItemUpdate(BaseModel):
    """`PATCH /api/grocery/{id}/items/{item_id}` body (spec.md §5.6).

    Every field is absent-by-default so the router can key off
    `model_fields_set`: an absent field is untouched, a present one (`null`
    included) is applied. `quantity` / `unit` are an atomic pair — exactly one
    present in the body is a 422 (N6).
    """

    checked: bool | None = None
    quantity: PositiveAmount | None = None
    unit: Annotated[str, Field(max_length=30)] | None = None
    item: Annotated[str, Field(min_length=1, max_length=200)] | None = None


class GroceryListItemRead(ORMModel):
    id: int
    item: str
    normalized_name: str
    quantity: float | None
    unit: str | None
    checked: bool
    checked_at: datetime | None
    submitted_at: datetime | None
    source: str  # "generated" | "manual"
    nettable: bool
    added_to_inventory: bool
    applied_quantity: float | None
    applied_unit: str | None


class GroceryListRead(ORMModel):
    id: int
    name: str
    status: str  # "active" | "archived"
    source_recipe_ids: list[int]
    created_at: datetime
    created_by: UserMini | None
    items: list[GroceryListItemRead]  # ordered by id
