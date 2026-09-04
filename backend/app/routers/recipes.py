from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.database import SessionDep, TransactionRoute
from app.models import CookLog, InventoryItem, Recipe, RecipeIngredient, _utcnow
from app.normalize import normalize_name
from app.schemas import (
    AvailabilityReport,
    CookLogRead,
    CookRequest,
    RecipeCreate,
    RecipeIngredientIn,
    RecipeRead,
    RecipeUpdate,
)
from app.security import CurrentUser, get_current_user
from app.services.ingredient_parse import parse_ingredient
from app.services.inventory_math import ReqLine, StockRow, check_availability, deduct_calc

router = APIRouter(
    prefix="/api/recipes",
    tags=["recipes"],
    route_class=TransactionRoute,
    dependencies=[Depends(get_current_user)],
)

# A pasted `str` element is bounded before it reaches the parser. This is the
# single guard that keeps every string sink fed by a pasted line inside its
# column: `raw_text`, and the parser's `item` / `note` — `item` falls back to the
# whole cleaned line when nothing parses (spec.md §5.2, R-4).
_PASTED_LINE_MAX = 200

_EAGER = (selectinload(Recipe.ingredients), selectinload(Recipe.created_by))


def _get_or_404(db: Session, recipe_id: int) -> Recipe:
    recipe = db.get(Recipe, recipe_id, options=_EAGER)
    if recipe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipe not found")
    return recipe


def _normalize_author_unit(unit: str | None) -> str | None:
    """Lower-case and strip one trailing `.` — the same shape the parser stores.

    Deliberately does *not* singularize: the stored value is the author's unit,
    display text only, and `2 cup flour` reads wrong. Every consumer that does
    arithmetic calls `normalize_unit_token`, which singularizes internally
    (spec.md §5.2).
    """
    if unit is None:
        return None
    unit = unit.strip().lower()
    if unit.endswith("."):
        unit = unit[:-1]
    return unit or None


def _build_ingredients(
    elements: list[RecipeIngredientIn | str],
) -> list[RecipeIngredient]:
    """Turn the request's mixed string/object elements into ordered child rows."""
    rows: list[dict] = []
    for element in elements:
        if isinstance(element, str):
            element = element[:_PASTED_LINE_MAX]
            if not element.strip():
                continue  # a blank pasted line is not an ingredient
            # `quantity` off the parser is trusted: it guarantees > 0 or None.
            rows.append({**parse_ingredient(element), "raw_text": element})
        else:
            if not (element.item and element.item.strip()):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="ingredient object requires a non-empty item",
                )
            rows.append(
                {
                    "quantity": element.quantity,
                    "unit": _normalize_author_unit(element.unit),
                    "item": element.item,
                    "note": element.note,
                    "raw_text": None,
                }
            )

    return [
        RecipeIngredient(
            position=position,
            normalized_name=normalize_name(row["item"]),
            **row,
        )
        for position, row in enumerate(rows)
    ]


def _req_lines(recipe: Recipe, multiplier: float) -> list[ReqLine]:
    """Recipe ingredients → `ReqLine`s with `multiplier` already folded in.

    A to-taste line stays `quantity=None` — never `None * multiplier` (R-1).
    """
    return [
        ReqLine(
            ingredient_id=ing.id,
            item=ing.item,
            normalized_name=ing.normalized_name,
            quantity=None if ing.quantity is None else ing.quantity * multiplier,
            unit=ing.unit,
        )
        for ing in recipe.ingredients
    ]


def _stock_rows(db: Session) -> list[StockRow]:
    """Every `inventory_items` row as an ORM-free `StockRow`."""
    return [
        StockRow(
            id=row.id,
            match_name=row.match_name,
            unit_bucket=row.unit_bucket,
            quantity_base=row.quantity_base,
        )
        for row in db.scalars(select(InventoryItem))
    ]


@router.get("", response_model=list[RecipeRead])
def list_recipes(db: SessionDep) -> list[Recipe]:
    stmt = (
        select(Recipe)
        .options(*_EAGER)
        .order_by(Recipe.created_at.desc(), Recipe.id.desc())
    )
    return list(db.scalars(stmt))


@router.post("", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe(payload: RecipeCreate, current_user: CurrentUser, db: SessionDep) -> Recipe:
    # Both stamps come from one `_utcnow()` call: two column defaults would fire
    # independently and leave a freshly created recipe with `created_at` a few
    # microseconds behind `updated_at` (spec.md §1, §7).
    now = _utcnow()
    recipe = Recipe(
        **payload.model_dump(exclude={"ingredients"}),
        created_at=now,
        updated_at=now,
        created_by_id=current_user.id,
        ingredients=_build_ingredients(payload.ingredients),
    )
    db.add(recipe)
    db.flush()  # populate ids / positions; TransactionRoute owns the commit
    return recipe


@router.get("/{recipe_id}", response_model=RecipeRead)
def get_recipe(recipe_id: int, db: SessionDep) -> Recipe:
    return _get_or_404(db, recipe_id)


@router.get("/{recipe_id}/availability", response_model=AvailabilityReport)
def recipe_availability(
    recipe_id: int,
    db: SessionDep,
    multiplier: float = Query(1.0, gt=0, allow_inf_nan=False),
) -> AvailabilityReport:
    """Per-ingredient availability against current stock (spec.md §5.3).

    `multiplier` is folded into each `ReqLine.quantity` here — a to-taste line
    stays `None`, never `None * multiplier` (R-1). `all_available` is true when
    every non-to-taste line is `ok` (an empty or all-to-taste recipe → true).
    """
    recipe = _get_or_404(db, recipe_id)

    lines = check_availability(_req_lines(recipe, multiplier), _stock_rows(db))
    all_available = all(
        line.status == "ok" for line in lines if line.status != "to_taste"
    )
    return AvailabilityReport(
        recipe_id=recipe.id,
        multiplier=multiplier,
        lines=lines,
        all_available=all_available,
    )


@router.post(
    "/{recipe_id}/cook",
    response_model=CookLogRead,
    status_code=status.HTTP_201_CREATED,
)
def cook_recipe(
    recipe_id: int, payload: CookRequest, current_user: CurrentUser, db: SessionDep
) -> CookLog:
    """Record a cook event and, when `deduct=true`, draw inventory down (spec.md §5.4).

    The `deduct_calc` proposal is applied with Core `UPDATE`s inside the
    request's single `BEGIN IMMEDIATE` transaction (`TransactionRoute` owns the
    commit). A Core `UPDATE` does not fire the ORM `onupdate`, so `updated_at`
    is bound explicitly. An `IntegrityError` / lock timeout rolls the whole
    thing back and surfaces as `409` via the global handlers.
    """
    recipe = _get_or_404(db, recipe_id)

    log = CookLog(
        recipe_id=recipe.id,
        recipe_title=recipe.title,
        multiplier=payload.multiplier,
        deducted=payload.deduct,
        cooked_by=current_user,
        deductions=[],
    )

    if payload.deduct:
        proposal = deduct_calc(
            _req_lines(recipe, payload.multiplier), _stock_rows(db)
        )
        now = _utcnow()
        for row_update in proposal.row_updates:
            db.execute(
                update(InventoryItem)
                .where(InventoryItem.id == row_update.row_id)
                .values(quantity_base=row_update.new_quantity_base, updated_at=now)
            )
        log.deductions = proposal.log_entries

    db.add(log)
    db.flush()  # populate id / cooked_at; TransactionRoute owns the commit
    return log


@router.get("/{recipe_id}/cook-logs", response_model=list[CookLogRead])
def list_cook_logs(recipe_id: int, db: SessionDep) -> list[CookLog]:
    """This recipe's made-history, newest-first, unpaginated (spec.md §5.4)."""
    _get_or_404(db, recipe_id)
    stmt = (
        select(CookLog)
        .options(selectinload(CookLog.cooked_by))
        .where(CookLog.recipe_id == recipe_id)
        .order_by(CookLog.cooked_at.desc(), CookLog.id.desc())
    )
    return list(db.scalars(stmt))


@router.put("/{recipe_id}", response_model=RecipeRead)
def update_recipe(recipe_id: int, payload: RecipeUpdate, db: SessionDep) -> Recipe:
    recipe = _get_or_404(db, recipe_id)
    # Build the replacement children before mutating anything, so a rejected
    # element leaves the recipe untouched.
    children = _build_ingredients(payload.ingredients)

    for key, value in payload.model_dump(exclude={"ingredients"}).items():
        setattr(recipe, key, value)
    # delete-orphan removes the displaced rows; ingredient IDs churn, and no
    # part of the API contract depends on their stability (spec.md §1).
    recipe.ingredients = children
    # Set explicitly rather than leaning on `onupdate`: a PUT that changes only
    # the ingredient list leaves the `recipes` row itself clean, and `onupdate`
    # would not fire.
    recipe.updated_at = _utcnow()

    db.flush()  # TransactionRoute owns the commit
    return recipe


@router.delete("/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipe(recipe_id: int, db: SessionDep) -> None:
    recipe = _get_or_404(db, recipe_id)
    db.delete(recipe)  # ingredients go with it via ON DELETE CASCADE
    db.flush()  # TransactionRoute owns the commit
