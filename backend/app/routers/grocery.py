"""Grocery lists (spec.md §5.6), prefix ``/api/grocery``.

`phase-6b` builds generation + list read/delete. `phase-6c` adds manual item
add + line edit + line delete (the N6 atomic `quantity`+`unit` pair and
reclassification). `phase-6d` adds submit (this file). Archive lands in
`phase-6e`.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, selectinload

from app.database import SessionDep, TransactionRoute
from app.models import GroceryList, GroceryListItem, InventoryItem, Recipe, _utcnow
from app.normalize import normalize_name
from app.schemas import (
    GroceryListCreate,
    GroceryListItemIn,
    GroceryListItemRead,
    GroceryListItemUpdate,
    GroceryListRead,
)
from app.security import CurrentUser, get_current_user
from app.services.inventory_math import (
    ReqLine,
    StockRow,
    add_to_inventory_calc,
    generate_lines,
)

router = APIRouter(
    prefix="/api/grocery",
    tags=["grocery"],
    route_class=TransactionRoute,
    dependencies=[Depends(get_current_user)],
)

_EAGER = (selectinload(GroceryList.items), selectinload(GroceryList.created_by))


def _get_or_404(db: Session, list_id: int) -> GroceryList:
    row = db.get(GroceryList, list_id, options=_EAGER)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list not found"
        )
    return row


def _get_item_or_404(
    db: Session, list_id: int, item_id: int
) -> tuple[GroceryList, GroceryListItem]:
    grocery_list = _get_or_404(db, list_id)
    item = next((it for it in grocery_list.items if it.id == item_id), None)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grocery list item not found"
        )
    return grocery_list, item


def _check_line_mutable(grocery_list: GroceryList, item: GroceryListItem) -> None:
    """`409` if the line is frozen (`added_to_inventory`) or the list is
    archived — shared PATCH/DELETE guard (spec.md §5.6)."""
    if item.added_to_inventory or grocery_list.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="line is frozen or list is archived",
        )


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


@router.post("", response_model=GroceryListRead, status_code=status.HTTP_201_CREATED)
def create_grocery_list(
    payload: GroceryListCreate, current_user: CurrentUser, db: SessionDep
) -> GroceryList:
    """Generate a persisted, consolidated shortfall list from selected recipes
    (spec.md §5.6). `recipe_ids` order drives both `ReqLine` construction and
    the resulting `source_recipe_ids` snapshot."""
    if len(set(payload.recipe_ids)) != len(payload.recipe_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="recipe_ids must not contain duplicates",
        )

    recipes = {
        r.id: r
        for r in db.scalars(
            select(Recipe)
            .options(selectinload(Recipe.ingredients))
            .where(Recipe.id.in_(payload.recipe_ids))
        )
    }
    missing = [rid for rid in payload.recipe_ids if rid not in recipes]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"recipe_ids not found: {missing}",
        )

    if not set(payload.multipliers).issubset(payload.recipe_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="multipliers keys must be a subset of recipe_ids",
        )

    reqs_by_recipe: list[list[ReqLine]] = []
    for rid in payload.recipe_ids:
        multiplier = payload.multipliers.get(rid, 1)
        reqs_by_recipe.append(
            [
                ReqLine(
                    ingredient_id=ing.id,
                    item=ing.item,
                    normalized_name=ing.normalized_name,
                    # A to-taste ingredient stays `None` — never `None * multiplier` (R-1).
                    quantity=None if ing.quantity is None else ing.quantity * multiplier,
                    unit=ing.unit,
                )
                for ing in recipes[rid].ingredients
            ]
        )

    lines = generate_lines(reqs_by_recipe, _stock_rows(db))

    grocery_list = GroceryList(
        name=payload.name or f"Groceries {_utcnow().date().isoformat()}",
        status="active",
        source_recipe_ids=payload.recipe_ids,
        created_by_id=current_user.id,
        items=[
            GroceryListItem(
                item=line.item,
                normalized_name=line.normalized_name,
                quantity=line.quantity,
                unit=line.unit,
                source="generated",
                checked=False,
                nettable=line.nettable,
                added_to_inventory=False,
            )
            for line in lines
        ],
    )
    db.add(grocery_list)
    db.flush()  # populate ids; TransactionRoute owns the commit
    return grocery_list


@router.get("", response_model=list[GroceryListRead])
def list_grocery_lists(
    db: SessionDep, status_: str | None = Query(None, alias="status")
) -> list[GroceryList]:
    stmt = select(GroceryList).options(*_EAGER)
    if status_ is not None:
        stmt = stmt.where(GroceryList.status == status_)
    stmt = stmt.order_by(GroceryList.created_at.desc(), GroceryList.id.desc())
    return list(db.scalars(stmt))


@router.get("/{list_id}", response_model=GroceryListRead)
def get_grocery_list(list_id: int, db: SessionDep) -> GroceryList:
    return _get_or_404(db, list_id)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grocery_list(list_id: int, db: SessionDep) -> None:
    """Any status. Cascades items (spec.md §5.6)."""
    grocery_list = _get_or_404(db, list_id)
    db.delete(grocery_list)
    db.flush()  # TransactionRoute owns the commit


@router.post(
    "/{list_id}/items",
    response_model=GroceryListItemRead,
    status_code=status.HTTP_201_CREATED,
)
def add_grocery_item(
    list_id: int, payload: GroceryListItemIn, db: SessionDep
) -> GroceryListItem:
    """Hand-add a manual line (spec.md §5.6). `404` list missing, `409` archived.
    Amounts are stored exactly as typed — no conversion."""
    grocery_list = _get_or_404(db, list_id)
    if grocery_list.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="list is archived"
        )

    item = GroceryListItem(
        grocery_list_id=list_id,
        item=payload.item,
        normalized_name=normalize_name(payload.item),
        quantity=payload.quantity,
        unit=payload.unit,
        source="manual",
        nettable=True,
        checked=False,
        added_to_inventory=False,
    )
    db.add(item)
    db.flush()  # TransactionRoute owns the commit
    return item


@router.patch("/{list_id}/items/{item_id}", response_model=GroceryListItemRead)
def update_grocery_item(
    list_id: int, item_id: int, payload: GroceryListItemUpdate, db: SessionDep
) -> GroceryListItem:
    """Edit a line's substance or checked state (spec.md §5.6, N6). `404` list
    or line missing; `409` if the line is frozen (`added_to_inventory`) or the
    list is archived; `422` if exactly one of `quantity`/`unit` is set —
    they're an atomic pair. Any `item`/`quantity`/`unit` edit reclassifies the
    line `source -> "manual"`, `nettable -> true`; a `checked`-only PATCH does
    not."""
    grocery_list, item = _get_item_or_404(db, list_id, item_id)
    _check_line_mutable(grocery_list, item)

    fields_set = payload.model_fields_set
    quantity_set = "quantity" in fields_set
    unit_set = "unit" in fields_set
    if quantity_set != unit_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="quantity and unit must be set together",
        )
    if "item" in fields_set and payload.item is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="item cannot be null",
        )

    reclassify = False
    if quantity_set and unit_set:
        item.quantity = payload.quantity  # as-is, no conversion (N6)
        item.unit = payload.unit
        reclassify = True
    if "item" in fields_set:
        item.item = payload.item
        item.normalized_name = normalize_name(payload.item)
        reclassify = True
    if "checked" in fields_set:
        item.checked = bool(payload.checked)
        item.checked_at = _utcnow() if payload.checked else None
    if reclassify:
        item.source = "manual"
        item.nettable = True

    db.flush()  # TransactionRoute owns the commit
    return item


@router.delete("/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grocery_item(list_id: int, item_id: int, db: SessionDep) -> None:
    """`404` list or line missing; `409` if the line is frozen or the list is
    archived (decision S5, spec.md §5.6)."""
    grocery_list, item = _get_item_or_404(db, list_id, item_id)
    _check_line_mutable(grocery_list, item)
    db.delete(item)
    db.flush()  # TransactionRoute owns the commit


@router.post("/{list_id}/submit", response_model=GroceryListRead)
def submit_grocery_list(
    list_id: int, current_user: CurrentUser, db: SessionDep
) -> GroceryList:
    """Apply every checked, unfrozen, quantified line into inventory once,
    inside this request's `BEGIN IMMEDIATE` transaction, and freeze it
    (spec.md §5.6). `404` list missing; `409` if the list is not `active`.

    Forward-only: an already-applied line is skipped, so re-submitting after
    checking more lines applies only the newly-eligible ones (shop today,
    finish tomorrow). `list.status` is never changed here — submit and
    archive are independent (`phase-6e`).
    """
    grocery_list = _get_or_404(db, list_id)
    if grocery_list.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="list is not active"
        )

    for line in grocery_list.items:
        if not line.checked or line.added_to_inventory or line.quantity is None:
            continue

        delta = add_to_inventory_calc(
            normalize_name(line.item), line.item, line.quantity, line.unit
        )

        # Additive upsert, same shape as `routers/inventory.py`'s `POST`
        # (spec.md §5.5): one `_utcnow()` binds `updated_at` on both the
        # insert and the conflict branch, since `INSERT ... ON CONFLICT`
        # bypasses the ORM's `onupdate`.
        now = _utcnow()
        stmt = sqlite_insert(InventoryItem).values(
            item=delta.item,
            normalized_name=delta.normalized_name,
            match_name=delta.match_name,
            unit_bucket=delta.unit_bucket,
            quantity_base=delta.add_base,
            display_unit=delta.display_unit,
            created_by_id=current_user.id,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["match_name", "unit_bucket"],
            set_={
                "quantity_base": InventoryItem.quantity_base + stmt.excluded.quantity_base,
                "display_unit": func.coalesce(
                    stmt.excluded.display_unit, InventoryItem.display_unit
                ),
                "updated_at": now,
            },
        )
        db.execute(stmt)

        line.applied_quantity = delta.canonical_added.amount
        line.applied_unit = delta.canonical_added.unit
        line.added_to_inventory = True
        line.submitted_at = now

    db.flush()  # TransactionRoute owns the commit
    return grocery_list
