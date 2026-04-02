"""Products API — browse, filter, and view price history."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.db import Product, ApiKey
from app.models.schemas import ProductOut, ProductDetailOut
from app.services.auth import authenticate, log_usage

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(
    request: Request,
    source: Optional[str] = Query(None, description="Filter by marketplace (grailed, fashionphile, 1stdibs)"),
    brand: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    is_sold: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    filters = []
    if source:
        filters.append(Product.source == source)
    if brand:
        filters.append(Product.brand.ilike(f"%{brand}%"))
    if category:
        filters.append(Product.category.ilike(f"%{category}%"))
    if min_price is not None:
        filters.append(Product.current_price >= min_price)
    if max_price is not None:
        filters.append(Product.current_price <= max_price)
    if is_sold is not None:
        filters.append(Product.is_sold == is_sold)

    stmt = select(Product).where(and_(*filters)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    products = result.scalars().all()
    await log_usage(db, api_key, "/products", "GET", 200)
    return products


@router.get("/{product_id}", response_model=ProductDetailOut)
async def get_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: ApiKey = Depends(authenticate),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.price_history))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    await log_usage(db, api_key, f"/products/{product_id}", "GET", 200)
    return product
