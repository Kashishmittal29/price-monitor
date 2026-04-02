"""Tests: ingest service, upsert logic, and price-change event emission."""

import pytest
from sqlalchemy import select

from app.models.db import Product, PriceHistory, PriceEvent
from app.services.ingest import _upsert_product
from tests.conftest import auth_headers

SAMPLE_PRODUCT = {
    "source": "grailed",
    "external_id": "test-001",
    "brand": "TestBrand",
    "model": "Test Model",
    "category": "apparel",
    "condition": None,
    "size": "M",
    "color": "Black",
    "image_url": "https://example.com/img.jpg",
    "product_url": "https://example.com/product",
    "currency": "USD",
    "current_price": 100.0,
    "is_sold": False,
}


@pytest.mark.asyncio
async def test_new_product_is_inserted(db_session):
    stats = {"loaded": 0, "updated": 0, "price_changes": 0, "errors": 0}
    await _upsert_product(db_session, SAMPLE_PRODUCT, stats)
    await db_session.commit()

    result = await db_session.execute(select(Product).where(Product.external_id == "test-001"))
    product = result.scalar_one_or_none()
    assert product is not None
    assert product.brand == "TestBrand"
    assert product.current_price == 100.0
    assert stats["loaded"] == 1


@pytest.mark.asyncio
async def test_initial_price_history_recorded(db_session):
    stats = {"loaded": 0, "updated": 0, "price_changes": 0, "errors": 0}
    await _upsert_product(db_session, SAMPLE_PRODUCT, stats)
    await db_session.commit()

    result = await db_session.execute(select(Product).where(Product.external_id == "test-001"))
    product = result.scalar_one()

    hist = await db_session.execute(
        select(PriceHistory).where(PriceHistory.product_id == product.id)
    )
    rows = hist.scalars().all()
    assert len(rows) == 1
    assert rows[0].price == 100.0


@pytest.mark.asyncio
async def test_price_change_emits_event(db_session):
    stats = {"loaded": 0, "updated": 0, "price_changes": 0, "errors": 0}
    await _upsert_product(db_session, SAMPLE_PRODUCT, stats)
    await db_session.commit()

    # Second pass with higher price
    updated = {**SAMPLE_PRODUCT, "current_price": 150.0}
    await _upsert_product(db_session, updated, stats)
    await db_session.commit()

    result = await db_session.execute(select(Product).where(Product.external_id == "test-001"))
    product = result.scalar_one()

    events = await db_session.execute(
        select(PriceEvent).where(PriceEvent.product_id == product.id)
    )
    evts = events.scalars().all()
    assert len(evts) == 1
    assert evts[0].old_price == 100.0
    assert evts[0].new_price == 150.0
    assert evts[0].delivered == False
    assert stats["price_changes"] == 1


@pytest.mark.asyncio
async def test_no_event_when_price_unchanged(db_session):
    stats = {"loaded": 0, "updated": 0, "price_changes": 0, "errors": 0}
    await _upsert_product(db_session, SAMPLE_PRODUCT, stats)
    await db_session.commit()
    await _upsert_product(db_session, SAMPLE_PRODUCT, stats)
    await db_session.commit()

    result = await db_session.execute(select(Product).where(Product.external_id == "test-001"))
    product = result.scalar_one()

    events = await db_session.execute(
        select(PriceEvent).where(PriceEvent.product_id == product.id)
    )
    assert len(events.scalars().all()) == 0
    assert stats["price_changes"] == 0
