"""Price-change events endpoint — consumers can poll for notifications."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.db import PriceEvent, ApiKey
from app.models.schemas import PriceEventOut
from app.services.auth import authenticate, log_usage
from app.services.notifications import process_pending_events

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[PriceEventOut])
async def list_events(
    request: Request,
    delivered: Optional[bool] = Query(None, description="Filter by delivery status"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    """Return recent price-change events. Poll this endpoint to receive notifications."""
    stmt = select(PriceEvent).order_by(PriceEvent.created_at.desc()).limit(limit)
    if delivered is not None:
        stmt = stmt.where(PriceEvent.delivered == delivered)
    result = await db.execute(stmt)
    events = result.scalars().all()
    await log_usage(db, api_key, "/events", "GET", 200)
    return events


@router.post("/process", tags=["events"])
async def process_events(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    """Manually trigger notification delivery for pending events."""
    count = await process_pending_events(db)
    await log_usage(db, api_key, "/events/process", "POST", 200)
    return {"delivered": count}
