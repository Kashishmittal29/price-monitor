from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PriceHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    price: float
    currency: str
    recorded_at: datetime


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    brand: Optional[str]
    model: Optional[str]
    category: Optional[str]
    condition: Optional[str]
    size: Optional[str]
    color: Optional[str]
    image_url: Optional[str]
    product_url: Optional[str]
    currency: str
    current_price: float
    is_sold: bool
    first_seen_at: datetime
    last_updated_at: datetime


class ProductDetailOut(ProductOut):
    price_history: list[PriceHistoryOut] = []


class PriceEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    old_price: Optional[float]
    new_price: float
    change_pct: Optional[float]
    created_at: datetime
    delivered: bool


class AnalyticsOut(BaseModel):
    total_products: int
    by_source: dict[str, int]
    avg_price_by_category: dict[str, float]
    total_price_changes_24h: int


class RefreshResultOut(BaseModel):
    loaded: int
    updated: int
    price_changes: int
    errors: int
