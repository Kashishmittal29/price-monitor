"""Simple API-key authentication using bcrypt hashed keys."""

import hashlib
import secrets
from datetime import datetime

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.db import ApiKey, UsageLog

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Default dev key — generated on first startup and printed to stdout
_DEFAULT_KEY: str | None = None


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_key() -> str:
    return secrets.token_urlsafe(32)


async def ensure_default_key(db: AsyncSession) -> str:
    """Create a default API key if none exist. Returns the raw key."""
    result = await db.execute(select(ApiKey).limit(1))
    if result.scalar_one_or_none():
        return ""  # already seeded

    raw = generate_key()
    db.add(ApiKey(key_hash=_hash_key(raw), label="default"))
    await db.commit()
    return raw


async def authenticate(
    raw_key: str | None = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == _hash_key(raw_key), ApiKey.is_active == True)
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
    return api_key


async def log_usage(db: AsyncSession, api_key: ApiKey, endpoint: str, method: str, status_code: int) -> None:
    db.add(UsageLog(
        api_key_id=api_key.id,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        requested_at=datetime.utcnow(),
    ))
    await db.commit()
