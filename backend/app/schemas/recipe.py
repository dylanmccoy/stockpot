"""Recipe schemas (spec.md §5.2)."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserMini
from app.schemas.common import ORMModel

# Constrained leaf types. Declared as `Annotated[...] | None` rather than
# `X | None = Field(...)` so the constraint lands on the value, not on the
# nullable union.
PositiveQuantity = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegativeMinutes = Annotated[int, Field(ge=0)]
Tag = Annotated[str, Field(max_length=50)]
Step = Annotated[str, Field(max_length=2000)]


class RecipeIngredientIn(BaseModel):
    """One requested ingredient, in structured (object) form.

    `extra="forbid"` lives here and nowhere else in the API: this is the one
    schema where a mistyped key yields a *successful wrong write* rather than an
    error. `{"item": "flour", "qty": 500}` would otherwise return 201 and store a
    to-taste row, because `quantity=None` is itself legitimate (spec.md §5.2).
    """

    model_config = ConfigDict(extra="forbid")

    quantity: PositiveQuantity | None = None
    unit: Annotated[str, Field(max_length=30)] | None = None
    # Optional at the schema level so the router can answer a blank/whitespace
    # `item` with the named 422 from §5.2 rather than a generic missing-field one.
    item: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    note: Annotated[str, Field(max_length=200)] | None = None


class RecipeIngredientRead(ORMModel):
    id: int
    position: int
    quantity: float | None
    unit: str | None
    item: str
    note: str | None
    normalized_name: str
    raw_text: str | None


class RecipeBase(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    notes: str = ""
    prep_time: NonNegativeMinutes | None = None
    cook_time: NonNegativeMinutes | None = None
    servings: PositiveQuantity | None = None
    cuisine: Annotated[str, Field(max_length=100)] | None = None
    # Free string, deliberately not URL-validated (spec.md §Mechanical defaults).
    source_url: Annotated[str, Field(max_length=500)] | None = None
    tags: Annotated[list[Tag], Field(max_length=100)] = []
    steps: Annotated[list[Step], Field(max_length=100)] = []


class RecipeCreate(RecipeBase):
    # A `str` element is a pasted line, parsed server-side; an object element is
    # already structured. Only `title` is required — a title-only recipe is legal.
    ingredients: list[RecipeIngredientIn | str] = []


class RecipeUpdate(RecipeCreate):
    """PUT fully replaces the recipe, ingredient children included."""


class RecipeRead(RecipeBase, ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime
    photo_path: str | None  # reserved for v2; always null in v1
    created_by: UserMini | None
    ingredients: list[RecipeIngredientRead]


class AvailabilityLine(ORMModel):
    """JSON shape of one `AvailabilityLineDTO` (spec.md §4 / §5.3), field for
    field. `from_attributes` reads it straight off the frozen dataclass."""

    ingredient_id: int
    item: str
    need: float | None
    need_unit: str
    group_key: str
    group_unit: str
    group_need: float | None
    group_have: float | None
    group_short: float | None
    status: str  # ok | short | missing | to_taste | have_uncertain
    nettable: bool


class AvailabilityReport(BaseModel):
    """`GET /api/recipes/{id}/availability` response (spec.md §5.3)."""

    recipe_id: int
    multiplier: float
    lines: list[AvailabilityLine]
    all_available: bool
