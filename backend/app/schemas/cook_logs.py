"""Cook-log schemas (spec.md §1 "cook_logs", §5.4)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import UserMini
from app.schemas.common import ORMModel


class CookRequest(BaseModel):
    """Body of `POST /api/recipes/{id}/cook` (spec.md §5.4)."""

    # `Annotated[...]` so the constraint lands on the value, matching the recipe
    # schemas' convention.
    multiplier: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 1
    deduct: bool = True


class CookDeductionRead(BaseModel):
    """JSON shape of one `CookLog.deductions[]` entry (spec.md §5.4).

    The DB column stays raw `JSON list[dict]` (written from `deduct_calc`'s
    `_entry()`); FastAPI validates every stored dict against this model on read,
    so a malformed or drifted entry is a loud `500`, not a silent shape change
    (N7). `extra="forbid"` makes a stray or renamed key a validation error.
    """

    model_config = ConfigDict(extra="forbid")

    item: str
    normalized_name: str | None
    requested: float | None
    requested_unit: str | None
    deducted: float | None
    deducted_unit: str | None
    inventory_unit: str | None
    before: float | None
    after: float | None
    applied: bool
    reason: Literal[
        "ok",
        "clamped to 0",
        "to taste",
        "not in inventory",
        "have uncertain (incompatible unit)",
    ]


class CookLogRead(ORMModel):
    """`CookLog` row as returned by the cook + made-history endpoints."""

    id: int
    recipe_id: int | None  # null once the recipe is deleted
    recipe_title: str  # snapshot
    multiplier: float
    deducted: bool
    cooked_at: datetime
    cooked_by: UserMini | None
    deductions: list[CookDeductionRead]  # [] when deducted=false


class CookLogList(BaseModel):
    """One page of the global cook-log feed (`GET /api/cook-logs`, spec.md §5.4)."""

    items: list[CookLogRead]
    total: int  # full count of all cook logs, ignoring pagination
    limit: int
    offset: int
