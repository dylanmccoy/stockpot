"""Global cook-log reads (spec.md §5.4), prefix ``/api/cook-logs``.

A paginated newest-first feed across every recipe, and a by-id detail read.
Both outlive the recipe: ``CookLog.recipe_id`` is ``ON DELETE SET NULL`` and
``recipe_title`` is a snapshot, so a log still resolves after its recipe is
deleted (spec.md §1).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.database import SessionDep, TransactionRoute
from app.models import CookLog
from app.schemas import CookLogList, CookLogRead
from app.security import get_current_user

router = APIRouter(
    prefix="/api/cook-logs",
    tags=["cook-logs"],
    route_class=TransactionRoute,
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=CookLogList)
def list_all_cook_logs(
    db: SessionDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> CookLogList:
    """Global made-history feed, ``cooked_at DESC, id DESC``, paginated."""
    total = db.scalar(select(func.count()).select_from(CookLog)) or 0
    stmt = (
        select(CookLog)
        .options(selectinload(CookLog.cooked_by))
        .order_by(CookLog.cooked_at.desc(), CookLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return CookLogList(
        items=list(db.scalars(stmt)), total=total, limit=limit, offset=offset
    )


@router.get("/{log_id}", response_model=CookLogRead)
def get_cook_log(log_id: int, db: SessionDep) -> CookLog:
    """One cook log by id; ``404`` if absent. Resolves after the recipe is gone."""
    log = db.get(CookLog, log_id, options=[selectinload(CookLog.cooked_by)])
    if log is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cook log not found"
        )
    return log
