"""Tests: marketplace collectors — normalisation correctness."""

import pytest

from app.collectors.grailed import GrailedCollector
from app.collectors.fashionphile import FashionphileCollector
from app.collectors.firstdibs import FirstDibsCollector


def test_grailed_normalise():
    raw = {
        "product_id": "abc-123",
        "brand": "amiri",
        "model": "Amiri Jeans",
        "price": 425.0,
        "size": None,
        "image_url": "https://img.grailed.com/x",
        "product_url": "https://grailed.com/1",
        "function_id": "apparel_authentication",
        "metadata": {"color": "Black", "is_sold": False},
    }
    result = GrailedCollector()._normalise(raw)
    assert result["source"] == "grailed"
    assert result["external_id"] == "abc-123"
    assert result["current_price"] == 425.0
    assert result["color"] == "Black"
    assert result["is_sold"] is False
    assert result["currency"] == "USD"


def test_fashionphile_normalise():
    raw = {
        "product_id": "fp-001",
        "brand": "Tiffany",
        "model": "Tiffany Earrings",
        "price": 1480.0,
        "currency": "USD",
        "condition": "Shows Wear",
        "image_url": "https://img.fashionphile.com/x",
        "product_url": "https://fashionphile.com/1",
        "metadata": {"garment_type": "jewelry"},
    }
    result = FashionphileCollector()._normalise(raw)
    assert result["source"] == "fashionphile"
    assert result["category"] == "jewelry"
    assert result["condition"] == "Shows Wear"
    assert result["current_price"] == 1480.0


def test_firstdibs_normalise():
    raw = {
        "product_id": "fd-001",
        "brand": "Chanel",
        "model": "Chanel Belt",
        "price": 2617.6,
        "product_url": "https://1stdibs.com/1",
        "metadata": {"condition_display": "New", "availability": "In Stock"},
    }
    result = FirstDibsCollector()._normalise(raw)
    assert result["source"] == "1stdibs"
    assert result["condition"] == "New"
    assert result["is_sold"] is False
    assert result["current_price"] == 2617.6


def test_grailed_collector_loads_sample_files():
    """Integration: GrailedCollector reads actual sample files."""
    import asyncio
    collector = GrailedCollector()
    items = asyncio.get_event_loop().run_until_complete(collector.collect())
    assert len(items) > 0
    for item in items:
        assert item["source"] == "grailed"
        assert item["current_price"] > 0
        assert "external_id" in item


def test_all_collector_prices_are_positive():
    """Ensure no collector returns a zero or negative price."""
    import asyncio

    async def run():
        results = []
        for cls in [GrailedCollector, FashionphileCollector, FirstDibsCollector]:
            items = await cls().collect()
            results.extend(items)
        return results

    items = asyncio.get_event_loop().run_until_complete(run())
    assert len(items) > 0
    for item in items:
        assert item["current_price"] > 0, f"Zero/negative price in {item}"
