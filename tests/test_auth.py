"""Tests: authentication, health check, and usage logging."""

import pytest
from tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_missing_api_key_returns_401(client):
    r = await client.get("/products")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_returns_403(client):
    r = await client.get("/products", headers={"X-API-Key": "wrong-key"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_valid_api_key_passes(client):
    r = await client.get("/products", headers=auth_headers())
    assert r.status_code == 200
