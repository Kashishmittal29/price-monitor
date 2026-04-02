"""
Product Price Monitoring System — main application entry point.

Run with:
    uvicorn main:app --reload
"""

import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models.database import init_db, AsyncSessionLocal
from app.services.auth import ensure_default_key
from app.services.notifications import notification_worker
from app.api import products, refresh, analytics, events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Product Price Monitor",
    description="Track competitor pricing across Grailed, Fashionphile, and 1stDibs.",
    version="1.0.0",
)

# --- Routers ---
app.include_router(products.router)
app.include_router(refresh.router)
app.include_router(analytics.router)
app.include_router(events.router)

# --- Static frontend ---
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# --- Global error handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# --- Startup ---
@app.on_event("startup")
async def startup():
    await init_db()
    async with AsyncSessionLocal() as db:
        raw_key = await ensure_default_key(db)
        if raw_key:
            logger.info("=" * 60)
            logger.info("DEFAULT API KEY (save this — shown only once):")
            logger.info("  %s", raw_key)
            logger.info("=" * 60)

    # Start background notification worker
    asyncio.create_task(notification_worker(interval=10))
    logger.info("Price Monitor started.")


@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Price Monitor API", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
