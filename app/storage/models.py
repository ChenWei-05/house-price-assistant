from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class CrawlTask(Base):
    __tablename__ = "crawl_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="xingfuli", index=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    district: Mapped[str | None] = mapped_column(String(80))
    keyword: Mapped[str | None] = mapped_column(String(200))
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=360)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="crawl_task")
    runs: Mapped[list[CrawlRun]] = relationship(back_populates="crawl_task")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source", "source_listing_id", name="uq_listings_source_listing_id"),
        UniqueConstraint("source", "url", name="uq_listings_source_url"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_listing_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    community: Mapped[str | None] = mapped_column(String(200), index=True)
    city: Mapped[str | None] = mapped_column(String(80), index=True)
    district: Mapped[str | None] = mapped_column(String(80), index=True)
    business_area: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(500))
    layout: Mapped[str | None] = mapped_column(String(80))
    area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    floor: Mapped[str | None] = mapped_column(String(80))
    total_floor: Mapped[int | None] = mapped_column(Integer)
    orientation: Mapped[str | None] = mapped_column(String(120))
    build_year: Mapped[int | None] = mapped_column(Integer)
    decoration: Mapped[str | None] = mapped_column(String(120))
    has_elevator: Mapped[bool | None] = mapped_column(Boolean)
    current_total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    current_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    current_status: Mapped[str] = mapped_column(String(30), default="active", nullable=False, index=True)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    removed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    snapshots: Mapped[list[ListingSnapshot]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    price_changes: Mapped[list[PriceChange]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    events: Mapped[list[ListingEvent]] = relationship(back_populates="listing", cascade="all, delete-orphan")


class ListingSnapshot(Base):
    __tablename__ = "listing_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False, index=True)
    crawl_task_id: Mapped[int] = mapped_column(ForeignKey("crawl_tasks.id"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    area: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    layout: Mapped[str | None] = mapped_column(String(80))
    floor: Mapped[str | None] = mapped_column(String(80))
    raw_data_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    snapshot_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="snapshots")
    crawl_task: Mapped[CrawlTask] = relationship(back_populates="snapshots")


class PriceChange(Base):
    __tablename__ = "price_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False, index=True)
    old_total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    new_total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    old_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    new_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    change_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="price_changes")


class ListingEvent(Base):
    __tablename__ = "listing_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    event_detail_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    listing: Mapped[Listing] = relationship(back_populates="events")


class CrawlRun(Base):
    __tablename__ = "crawl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crawl_task_id: Mapped[int] = mapped_column(ForeignKey("crawl_tasks.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False)
    stats_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    crawl_task: Mapped[CrawlTask] = relationship(back_populates="runs")

