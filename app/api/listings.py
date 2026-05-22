from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.events import ListingEventRead
from app.schemas.listings import ListingRead, ListingSnapshotRead, PriceChangeRead
from app.storage.database import get_session
from app.storage.repositories import ListingRepository


router = APIRouter(prefix="/api/listings", tags=["listings"])


@router.get("", response_model=list[ListingRead])
def list_listings(
    source: str | None = None,
    city: str | None = None,
    district: str | None = None,
    community: str | None = None,
    keyword: str | None = None,
    min_total_price: Decimal | None = None,
    max_total_price: Decimal | None = None,
    min_unit_price: Decimal | None = None,
    max_unit_price: Decimal | None = None,
    min_area: Decimal | None = None,
    max_area: Decimal | None = None,
    layout: str | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_session),
) -> list[object]:
    filters = {
        "source": source,
        "city": city,
        "district": district,
        "community": community,
        "keyword": keyword,
        "min_total_price": min_total_price,
        "max_total_price": max_total_price,
        "min_unit_price": min_unit_price,
        "max_unit_price": max_unit_price,
        "min_area": min_area,
        "max_area": max_area,
        "layout": layout,
        "status": status,
    }
    return ListingRepository(db).list(filters, page=page, page_size=page_size)


@router.get("/{listing_id}", response_model=ListingRead)
def get_listing(listing_id: int, db: Session = Depends(get_session)) -> object:
    listing = ListingRepository(db).get(listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="房源不存在")
    return listing


@router.get("/{listing_id}/snapshots", response_model=list[ListingSnapshotRead])
def get_listing_snapshots(listing_id: int, db: Session = Depends(get_session)) -> list[object]:
    return ListingRepository(db).snapshots(listing_id)


@router.get("/{listing_id}/price-changes", response_model=list[PriceChangeRead])
def get_listing_price_changes(listing_id: int, db: Session = Depends(get_session)) -> list[object]:
    return ListingRepository(db).price_changes(listing_id)


@router.get("/{listing_id}/events", response_model=list[ListingEventRead])
def get_listing_events(listing_id: int, db: Session = Depends(get_session)) -> list[object]:
    return ListingRepository(db).events(listing_id)

