"""Inventory CRUD (spec.md §5.5), prefix ``/api/inventory``.

``POST`` is an additive upsert on ``(match_name, unit_bucket)``; the
absolute-replacement ``PATCH`` lands in phase-4c.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionDep, TransactionRoute
from app.models import InventoryItem, _utcnow
from app.schemas import InventoryItemCreate, InventoryItemRead
from app.security import CurrentUser, get_current_user
from app.services.inventory_math import add_to_inventory_calc

router = APIRouter(
    prefix="/api/inventory",
    tags=["inventory"],
    route_class=TransactionRoute,
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[InventoryItemRead])
def list_inventory(db: SessionDep) -> list[InventoryItem]:
    stmt = select(InventoryItem).order_by(
        InventoryItem.match_name.asc(), InventoryItem.unit_bucket.asc()
    )
    return list(db.scalars(stmt))


@router.post("", response_model=InventoryItemRead, status_code=status.HTTP_201_CREATED)
def add_inventory(
    payload: InventoryItemCreate, current_user: CurrentUser, db: SessionDep
) -> InventoryItem:
    delta = add_to_inventory_calc(
        payload.match_name, payload.item, payload.quantity, payload.unit
    )
    if not delta.match_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="match_name normalizes to empty",
        )

    # One `_utcnow()` binds `updated_at` on both the insert and the conflict
    # branch: `INSERT ... ON CONFLICT` bypasses the ORM's `onupdate`, and
    # SQLite's `CURRENT_TIMESTAMP` is naive and second-precision (spec.md §5.5).
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
            # `item` / `normalized_name` / `created_by_id` are untouched on
            # conflict.
            "quantity_base": InventoryItem.quantity_base + stmt.excluded.quantity_base,
            "display_unit": func.coalesce(
                stmt.excluded.display_unit, InventoryItem.display_unit
            ),
            "updated_at": now,
        },
    )
    db.execute(stmt)

    # Re-read rather than `RETURNING *`: the row was never loaded into this
    # session's identity map, so a plain SELECT is the row the upsert just wrote.
    return db.scalar(
        select(InventoryItem).where(
            InventoryItem.match_name == delta.match_name,
            InventoryItem.unit_bucket == delta.unit_bucket,
        )
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory(item_id: int, db: SessionDep) -> None:
    row = db.get(InventoryItem, item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
        )
    db.delete(row)
    db.flush()  # TransactionRoute owns the commit
