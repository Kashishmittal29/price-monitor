"""
Notification service using a durable event-log pattern.

Why event log over webhooks/polling?
- Webhooks require consumers to expose HTTP endpoints — extra infra.
- Direct polling couples consumers to our DB.
- Event log: we write events atomically with price changes (no lost events),
  workers deliver asynchronously (no blocking fetch pipeline), and
  retry_count prevents infinite loops on bad consumers.

At scale: swap the SQLite poll loop for a Kafka/SQS producer that reads
from the same event table — the interface stays identical.
"""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import AsyncSessionLocal
from app.models.db import PriceEvent

logger = logging.getLogger(__name__)

MAX_RETRIES = 5


async def deliver_event(event: PriceEvent) -> bool:
    """
    Placeholder delivery: log the event.
    In production: POST to registered webhook URLs or push to a message queue.
    Returns True on success.
    """
    logger.info(
        "PRICE CHANGE | product_id=%s | %.2f -> %.2f (%.1f%%)",
        event.product_id,
        event.old_price or 0,
        event.new_price,
        event.change_pct or 0,
    )
    return True


async def process_pending_events(db: AsyncSession) -> int:
    """Deliver all undelivered events; mark them done or increment retry."""
    result = await db.execute(
        select(PriceEvent)
        .where(PriceEvent.delivered == False, PriceEvent.retry_count < MAX_RETRIES)
        .order_by(PriceEvent.created_at)
        .limit(100)
    )
    events = result.scalars().all()
    delivered = 0

    for event in events:
        try:
            success = await deliver_event(event)
            if success:
                event.delivered = True
                event.delivered_at = datetime.utcnow()
                delivered += 1
            else:
                event.retry_count += 1
        except Exception as exc:
            logger.error("Failed to deliver event %s: %s", event.id, exc)
            event.retry_count += 1

    await db.commit()
    return delivered


async def notification_worker(interval: int = 10) -> None:
    """Background coroutine: poll for undelivered events every `interval` seconds."""
    logger.info("Notification worker started (interval=%ds)", interval)
    while True:
        try:
            async with AsyncSessionLocal() as db:
                count = await process_pending_events(db)
                if count:
                    logger.info("Delivered %d price-change events", count)
        except Exception as exc:
            logger.error("Notification worker error: %s", exc)
        await asyncio.sleep(interval)
