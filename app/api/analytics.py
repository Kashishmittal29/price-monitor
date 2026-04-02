"""Analytics endpoint — aggregate stats across all products."""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.db import Product, PriceEvent, ApiKey
from app.models.schemas import AnalyticsOut
from app.services.auth import authenticate, log_usage

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
async def get_analytics(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    # Total product count
    total_res = await db.execute(select(func.count(Product.id)))
    total_products = total_res.scalar_one() or 0

    # Products by source
    source_res = await db.execute(
        select(Product.source, func.count(Product.id)).group_by(Product.source)
    )
    by_source = {row[0]: row[1] for row in source_res.all()}

    # Average price by category (skip null/empty categories)
    cat_res = await db.execute(
        select(Product.category, func.avg(Product.current_price))
        .where(Product.category != None, Product.category != "")
        .group_by(Product.category)
    )
    avg_price_by_category = {
        row[0]: round(row[1], 2) for row in cat_res.all() if row[1] is not None
    }

    # Price changes in last 24 hours
    since = datetime.utcnow() - timedelta(hours=24)
    changes_res = await db.execute(
        select(func.count(PriceEvent.id)).where(PriceEvent.created_at >= since)
    )
    total_price_changes_24h = changes_res.scalar_one() or 0

    await log_usage(db, api_key, "/analytics", "GET", 200)
    return AnalyticsOut(
        total_products=total_products,
        by_source=by_source,
        avg_price_by_category=avg_price_by_category,
        total_price_changes_24h=total_price_changes_24h,
    )
