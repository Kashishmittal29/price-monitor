"""Tests: analytics and price-events endpoints."""

import pytest
from datetime import datetime

from app.models.db import Product, PriceEvent
from tests.conftest import auth_headers


async def seed_minimal(db):
    p = Product(
        source="1stdibs", external_id="dibs-01", brand="Chanel",
        model="Chanel Belt", category="belts",
        product_url="https://1stdibs.com/1",
        currency="USD", current_price=2500.0, is_sold=False,
        first_seen_at=datetime.utcnow(), last_updated_at=datetime.utcnow(),
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.asyncio
async def test_analytics_totals(client, db_session):
    await seed_minimal(db_session)
    r = await client.get("/analytics", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert data["total_products"] >= 1
    assert "by_source" in data
    assert "1stdibs" in data["by_source"]


@pytest.mark.asyncio
async def test_analytics_avg_price_by_category(client, db_session):
    await seed_minimal(db_session)
    r = await client.get("/analytics", headers=auth_headers())
    data = r.json()
    assert "belts" in data["avg_price_by_category"]
    assert data["avg_price_by_category"]["belts"] == 2500.0


@pytest.mark.asyncio
async def test_events_list(client, db_session):
    p = await seed_minimal(db_session)
    db_session.add(PriceEvent(
        product_id=p.id, old_price=2000.0, new_price=2500.0,
        change_pct=25.0, created_at=datetime.utcnow(), delivered=False,
    ))
    await db_session.commit()

    r = await client.get("/events", headers=auth_headers())
    assert r.status_code == 200
    events = r.json()
    assert len(events) >= 1
    assert events[0]["new_price"] == 2500.0


@pytest.mark.asyncio
async def test_events_filter_by_delivered(client, db_session):
    p = await seed_minimal(db_session)
    db_session.add(PriceEvent(
        product_id=p.id, old_price=2000.0, new_price=2500.0,
        change_pct=25.0, created_at=datetime.utcnow(), delivered=True,
        delivered_at=datetime.utcnow(),
    ))
    await db_session.commit()

    r = await client.get("/events?delivered=false", headers=auth_headers())
    assert r.status_code == 200
    assert all(not e["delivered"] for e in r.json())
