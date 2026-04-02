"""Tests: products API — listing, filtering, and detail view."""

import pytest
from sqlalchemy import select
from datetime import datetime

from app.models.db import Product, PriceHistory
from tests.conftest import auth_headers


async def seed_product(db, overrides=None):
    data = {
        "source": "grailed",
        "external_id": "prod-api-01",
        "brand": "Amiri",
        "model": "Amiri Jeans",
        "category": "apparel",
        "condition": None,
        "size": "M",
        "color": "Black",
        "image_url": None,
        "product_url": "https://grailed.com/1",
        "currency": "USD",
        "current_price": 500.0,
        "is_sold": False,
        "first_seen_at": datetime.utcnow(),
        "last_updated_at": datetime.utcnow(),
    }
    if overrides:
        data.update(overrides)
    product = Product(**data)
    db.add(product)
    await db.commit()
    await db.refresh(product)
    db.add(PriceHistory(product_id=product.id, price=500.0, currency="USD", recorded_at=datetime.utcnow()))
    await db.commit()
    return product


@pytest.mark.asyncio
async def test_list_products_returns_all(client, db_session):
    await seed_product(db_session)
    r = await client.get("/products", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["brand"] == "Amiri"


@pytest.mark.asyncio
async def test_filter_by_source(client, db_session):
    await seed_product(db_session, {"source": "fashionphile", "external_id": "f-01"})
    r = await client.get("/products?source=fashionphile", headers=auth_headers())
    assert r.status_code == 200
    assert all(p["source"] == "fashionphile" for p in r.json())


@pytest.mark.asyncio
async def test_filter_by_price_range(client, db_session):
    await seed_product(db_session, {"external_id": "cheap-01", "current_price": 50.0})
    await seed_product(db_session, {"external_id": "pricey-01", "current_price": 2000.0})
    r = await client.get("/products?min_price=100&max_price=1000", headers=auth_headers())
    assert r.status_code == 200
    for p in r.json():
        assert 100 <= p["current_price"] <= 1000


@pytest.mark.asyncio
async def test_product_detail_includes_history(client, db_session):
    p = await seed_product(db_session)
    r = await client.get(f"/products/{p.id}", headers=auth_headers())
    assert r.status_code == 200
    data = r.json()
    assert "price_history" in data
    assert len(data["price_history"]) >= 1


@pytest.mark.asyncio
async def test_product_not_found_returns_404(client, db_session):
    r = await client.get("/products/99999", headers=auth_headers())
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_invalid_price_range_returns_422(client, db_session):
    r = await client.get("/products?min_price=-1", headers=auth_headers())
    assert r.status_code == 422
