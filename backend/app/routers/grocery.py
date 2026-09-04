"""Grocery lists (spec.md §5.6), prefix ``/api/grocery``.

`phase-6b` builds generation + list read/delete only: manual item add, line
edit, submit, and archive land in `phase-6c`-`6e` (spec.md §5.6, later routes).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import SessionDep, TransactionRoute
from app.models import GroceryList, GroceryListItem, InventoryItem, Recipe, _utcnow
from app.schemas import GroceryListCreate, GroceryListRead
from app.security import CurrentUser, get_current_user
from app.services.inventory_math import ReqLine, StockRow, generate_lines

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
