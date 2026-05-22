from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class ListingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_listing_id: str
    url: str
    title: str
    community: str | None
    city: str | None
    district: str | None
    business_area: str | None
    address: str | None
    layout: str | None
    area: Decimal | None
    floor: str | None
    total_floor: int | None
    orientation: str | None
    build_year: int | None
    decoration: str | None
    has_elevator: bool | None
    current_total_price: Decimal | None
    current_unit_price: Decimal | None
    current_status: str
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    removed_at: dt.datetime | None
    missing_count: int
    created_at: dt.datetime
    updated_at: dt.datetime


class ListingSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    crawl_task_id: int
    title: str | None
    total_price: Decimal | None
    unit_price: Decimal | None
    area: Decimal | None
    layout: str | None
    floor: str | None
    raw_data_json: dict[str, Any]
    snapshot_at: dt.datetime


class PriceChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    old_total_price: Decimal | None
    new_total_price: Decimal | None
    old_unit_price: Decimal | None
    new_unit_price: Decimal | None
    change_amount: Decimal | None
    change_percent: Decimal | None
    change_type: str
    detected_at: dt.datetime

