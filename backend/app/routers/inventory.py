"""Inventory CRUD (spec.md §5.5), prefix ``/api/inventory``.

``POST`` is an additive upsert on ``(match_name, unit_bucket)``; ``PATCH`` is an
absolute replacement driven by ``body.model_fields_set``.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionDep, TransactionRoute
from app.models import InventoryItem, _utcnow
from app.normalize import normalize_name
from app.schemas import InventoryItemCreate, InventoryItemRead, InventoryItemUpdate
from app.security import CurrentUser, get_current_user
from app.services.inventory_math import add_to_inventory_calc
from app.units import bucket_of, normalize_unit_token, to_base

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


@router.patch("/{item_id}", response_model=InventoryItemRead)
def update_inventory(
    item_id: int, payload: InventoryItemUpdate, db: SessionDep
) -> InventoryItem:
    """Absolute replacement (spec.md §5.5). Every branch is gated on
    ``S = body.model_fields_set`` — an absent field is never touched, a
    present-and-null field is a 422 (not a clear)."""
    row = db.get(InventoryItem, item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
        )

    fields_set = payload.model_fields_set
    if not fields_set:
        return row  # 200 no-op — nothing set, `updated_at` untouched

    for field in ("item", "match_name", "quantity"):
        if field in fields_set and getattr(payload, field) is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{field} cannot be null",
            )

    if "quantity" in fields_set and "unit" not in fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="unit is required when setting quantity",  # decision S2
        )

    if "unit" in fields_set:
        # `unit:null` on a non-COUNT row lands here as "count" != row.unit_bucket;
        # on a COUNT row it is allowed and clears the display preference.
        if bucket_of(normalize_unit_token(payload.unit)) != row.unit_bucket:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="unit changes the bucket; remove and re-add",
            )

    normalized_match: str | None = None
    if "match_name" in fields_set:
        normalized_match = normalize_name(payload.match_name)
        if normalized_match == "":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="match_name normalizes to empty",
            )
        clash = db.scalar(
            select(InventoryItem).where(
                InventoryItem.match_name == normalized_match,
                InventoryItem.unit_bucket == row.unit_bucket,
                InventoryItem.id != row.id,
            )
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="match_name already in use for this bucket",
            )

    # ---- apply (all within the single BEGIN IMMEDIATE transaction) ----
    if "quantity" in fields_set:
        amount = max(payload.quantity, 0.0)
        if row.unit_bucket.startswith("opaque:") or normalize_unit_token(payload.unit) is None:
            row.quantity_base = amount  # opaque token / no unit keeps the raw amount
        else:
            row.quantity_base = to_base(amount, payload.unit)[0]  # ABSOLUTE, canonical
    if "unit" in fields_set:
        row.display_unit = payload.unit  # display preference only, never math
    if "match_name" in fields_set:
        row.match_name = normalized_match
    if "item" in fields_set:
        row.item = payload.item
        row.normalized_name = normalize_name(payload.item)
    row.updated_at = _utcnow()

    db.flush()  # TransactionRoute owns the commit
    return row


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory(item_id: int, db: SessionDep) -> None:
    row = db.get(InventoryItem, item_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found"
        )
    db.delete(row)
    db.flush()  # TransactionRoute owns the commit
