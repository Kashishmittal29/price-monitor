"""
SQLAlchemy ORM models for the price monitoring system.

Schema decisions:
- products: normalized product records keyed by (source, external_id).
  A product from Grailed and Fashionphile may share a brand/model but they are
  separate listings, so we treat them as distinct rows and leave cross-source
  deduplication to analytics queries rather than forcing a brittle merge.
- price_history: append-only table.  Index on (product_id, recorded_at DESC)
  means point-in-time lookups stay O(log n) even with millions of rows.
  For true scale we'd partition by month (PostgreSQL range partitioning) or
  archive old rows to cold storage; SQLite users can use page compression.
- price_events: durable event log for notifications.  Written inside the same
  DB transaction as the price_history insert, so events are never lost even if
  the notification worker crashes.  Workers poll this table and mark events
  delivered, giving at-least-once delivery with idempotent consumers.
- api_keys / usage_log: simple token auth + per-request audit trail.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime,
    ForeignKey, Text, Index, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Source marketplace: grailed | fashionphile | 1stdibs
    source = Column(String(50), nullable=False, index=True)
    # Stable external identifier from the source JSON (product_id field)
    external_id = Column(String(255), nullable=False)
    brand = Column(String(255), index=True)
    model = Column(String(512))
    category = Column(String(255), index=True)   # garment_type / function_id
    condition = Column(String(100))
    size = Column(String(100))
    color = Column(String(100))
    image_url = Column(Text)
    product_url = Column(Text)
    currency = Column(String(10), default="USD")
    # Current / latest price — denormalised for fast list queries
    current_price = Column(Float, nullable=False)
    is_sold = Column(Boolean, default=False)
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    price_history = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    price_events = relationship(
        "PriceEvent", back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_source_external_id"),
    )

    def __repr__(self) -> str:
        return f"<Product id={self.id} source={self.source} brand={self.brand}>"


class PriceHistory(Base):
    """
    Append-only price log.  Never update or delete rows here.
    At millions of rows, add a composite index on (product_id, recorded_at)
    and consider PostgreSQL range partitioning by month.
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    product = relationship("Product", back_populates="price_history")

    __table_args__ = (
        Index("ix_price_history_product_recorded", "product_id", "recorded_at"),
    )


class PriceEvent(Base):
    """
    Durable event log written atomically with each price change.
    Notification workers poll undelivered events and mark them delivered.
    This gives at-least-once delivery without blocking the fetch pipeline.
    """
    __tablename__ = "price_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    old_price = Column(Float)
    new_price = Column(Float, nullable=False)
    change_pct = Column(Float)          # (new-old)/old * 100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivered = Column(Boolean, default=False, index=True)
    delivered_at = Column(DateTime)
    retry_count = Column(Integer, default=0)

    product = relationship("Product", back_populates="price_events")


class ApiKey(Base):
    """Simple static API-key authentication."""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key_hash = Column(String(255), unique=True, nullable=False)
    label = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    usage_logs = relationship("UsageLog", back_populates="api_key", cascade="all, delete-orphan")


class UsageLog(Base):
    """Per-request audit trail."""
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(Integer, ForeignKey("api_keys.id", ondelete="CASCADE"), nullable=False)
    endpoint = Column(String(255))
    method = Column(String(10))
    status_code = Column(Integer)
    requested_at = Column(DateTime, default=datetime.utcnow)

    api_key = relationship("ApiKey", back_populates="usage_logs")
