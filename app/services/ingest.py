"""
Ingest service: runs all collectors concurrently, upserts products into the DB,
records price history, and writes price-change events atomically.

Design: asyncio.gather() runs collectors in parallel (simulates concurrent HTTP
scrapes).  All DB writes happen inside a single transaction per collector batch
so we never get partial state.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors import ALL_COLLECTORS
from app.models.db import Product, PriceHistory, PriceEvent

logger = logging.getLogger(__name__)


async def run_refresh(db: AsyncSession) -> dict[str, int]:
    """
    Collect from all marketplaces concurrently and ingest into DB.
    Returns summary counters.
    """
    collectors = [cls() for cls in ALL_COLLECTORS]
    batches: list[list[dict]] = await asyncio.gather(
        *[c.collect() for c in collectors], return_exceptions=False
    )

    stats = {"loaded": 0, "updated": 0, "price_changes": 0, "errors": 0}

    for items in batches:
        for item in items:
            try:
                await _upsert_product(db, item, stats)
            except Exception as exc:
                logger.error("Ingest error for %s/%s: %s", item.get("source"), item.get("external_id"), exc)
                stats["errors"] += 1

    await db.commit()
    return stats


async def _upsert_product(db: AsyncSession, data: dict[str, Any], stats: dict) -> None:
    result = await db.execute(
        select(Product).where(
            Product.source == data["source"],
            Product.external_id == data["external_id"],
        )
    )
    product: Product | None = result.scalar_one_or_none()

    if product is None:
        # New listing
        product = Product(**{k: v for k, v in data.items()})
        db.add(product)
        await db.flush()  # get product.id
        # Record initial price
        db.add(PriceHistory(
            product_id=product.id,
            price=product.current_price,
            currency=product.currency,
            recorded_at=datetime.utcnow(),
        ))
        stats["loaded"] += 1
    else:
        old_price = product.current_price
        new_price = float(data["current_price"])
        stats["updated"] += 1

        if abs(new_price - old_price) > 0.001:
            # Price changed — record history and emit event atomically
            product.current_price = new_price
            product.last_updated_at = datetime.utcnow()
            db.add(PriceHistory(
                product_id=product.id,
                price=new_price,
                currency=data.get("currency", "USD"),
                recorded_at=datetime.utcnow(),
            ))
            change_pct = ((new_price - old_price) / old_price * 100) if old_price else None
            db.add(PriceEvent(
                product_id=product.id,
                old_price=old_price,
                new_price=new_price,
                change_pct=round(change_pct, 2) if change_pct is not None else None,
                created_at=datetime.utcnow(),
                delivered=False,
            ))
            stats["price_changes"] += 1

        # Update other mutable fields
        for field in ("condition", "is_sold", "image_url", "product_url"):
            if field in data:
                setattr(product, field, data[field])
