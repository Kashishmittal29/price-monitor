"""Refresh endpoint — triggers async data collection from all marketplaces."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.db import ApiKey
from app.models.schemas import RefreshResultOut
from app.services.auth import authenticate, log_usage
from app.services.ingest import run_refresh

router = APIRouter(prefix="/refresh", tags=["refresh"])


@router.post("", response_model=RefreshResultOut)
async def trigger_refresh(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    """
    Collect fresh data from all configured marketplaces, detect price changes,
    and emit price-change events.  This is idempotent — running it multiple
    times without real data changes causes no side effects.
    """
    stats = await run_refresh(db)
    await log_usage(db, api_key, "/refresh", "POST", 200)
    return RefreshResultOut(**stats)
