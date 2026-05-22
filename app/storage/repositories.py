from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, desc, func, select
from sqlalchemy.orm import Session

from app.crawler.base import CrawledListing
from app.storage.models import CrawlRun, CrawlTask, Listing, ListingEvent, ListingSnapshot, PriceChange


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


class CrawlTaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self) -> list[CrawlTask]:
        return list(self.db.scalars(select(CrawlTask).order_by(desc(CrawlTask.created_at))))

    def enabled(self) -> list[CrawlTask]:
        return list(self.db.scalars(select(CrawlTask).where(CrawlTask.enabled.is_(True))))

    def get(self, task_id: int) -> CrawlTask | None:
        return self.db.get(CrawlTask, task_id)

    def create(self, data: dict[str, Any]) -> CrawlTask:
        task = CrawlTask(**data)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update(self, task: CrawlTask, data: dict[str, Any]) -> CrawlTask:
        for key, value in data.items():
            if value is not None:
                setattr(task, key, value)
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete(self, task: CrawlTask) -> None:
        self.db.delete(task)
        self.db.commit()


class ListingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, filters: dict[str, Any], page: int = 1, page_size: int = 50) -> list[Listing]:
        statement = select(Listing)
        statement = self._apply_filters(statement, filters)
        statement = statement.order_by(desc(Listing.last_seen_at))
        statement = statement.offset(max(page - 1, 0) * page_size).limit(page_size)
        return list(self.db.scalars(statement))

    def get(self, listing_id: int) -> Listing | None:
        return self.db.get(Listing, listing_id)

    def find_existing(self, listing: CrawledListing) -> Listing | None:
        source_id_statement = select(Listing).where(
            and_(
                Listing.source == listing.source,
                Listing.source_listing_id == listing.source_listing_id,
            )
        )
        found = self.db.scalar(source_id_statement)
        if found:
            return found
        return self.db.scalar(
            select(Listing).where(
                and_(
                    Listing.source == listing.source,
                    Listing.url == listing.url,
                )
            )
        )

    def create_from_crawled(self, listing: CrawledListing, now: dt.datetime) -> Listing:
        row = Listing(
            source=listing.source,
            source_listing_id=listing.source_listing_id,
            url=listing.url,
            title=listing.title,
            community=listing.community,
            city=listing.city,
            district=listing.district,
            business_area=listing.business_area,
            address=listing.address,
            layout=listing.layout,
            area=listing.area,
            floor=listing.floor,
            total_floor=listing.total_floor,
            orientation=listing.orientation,
            build_year=listing.build_year,
            decoration=listing.decoration,
            has_elevator=listing.has_elevator,
            current_total_price=listing.total_price,
            current_unit_price=listing.unit_price,
            current_status="active",
            first_seen_at=now,
            last_seen_at=now,
            missing_count=0,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def update_from_crawled(self, row: Listing, listing: CrawledListing, now: dt.datetime) -> None:
        row.url = listing.url
        row.title = listing.title
        row.community = listing.community or row.community
        row.city = listing.city or row.city
        row.district = listing.district or row.district
        row.business_area = listing.business_area or row.business_area
        row.address = listing.address or row.address
        row.layout = listing.layout or row.layout
        row.area = listing.area or row.area
        row.floor = listing.floor or row.floor
        row.total_floor = listing.total_floor or row.total_floor
        row.orientation = listing.orientation or row.orientation
        row.build_year = listing.build_year or row.build_year
        row.decoration = listing.decoration or row.decoration
        row.has_elevator = listing.has_elevator if listing.has_elevator is not None else row.has_elevator
        row.current_total_price = listing.total_price if listing.total_price is not None else row.current_total_price
        row.current_unit_price = listing.unit_price if listing.unit_price is not None else row.current_unit_price
        row.current_status = "active"
        row.last_seen_at = now
        row.removed_at = None
        row.missing_count = 0

    def add_snapshot(self, listing_id: int, task_id: int, listing: CrawledListing, now: dt.datetime) -> ListingSnapshot:
        snapshot = ListingSnapshot(
            listing_id=listing_id,
            crawl_task_id=task_id,
            title=listing.title,
            total_price=listing.total_price,
            unit_price=listing.unit_price,
            area=listing.area,
            layout=listing.layout,
            floor=listing.floor,
            raw_data_json=listing.raw_data,
            snapshot_at=now,
        )
        self.db.add(snapshot)
        return snapshot

    def add_event(self, listing_id: int, event_type: str, detail: dict[str, Any], now: dt.datetime) -> ListingEvent:
        event = ListingEvent(
            listing_id=listing_id,
            event_type=event_type,
            event_detail_json=_json_safe(detail),
            created_at=now,
        )
        self.db.add(event)
        return event

    def add_price_change(
        self,
        listing_id: int,
        change_type: str,
        detail: dict[str, Any],
        now: dt.datetime,
    ) -> PriceChange:
        price_change = PriceChange(
            listing_id=listing_id,
            old_total_price=detail.get("old_total_price"),
            new_total_price=detail.get("new_total_price"),
            old_unit_price=detail.get("old_unit_price"),
            new_unit_price=detail.get("new_unit_price"),
            change_amount=detail.get("change_amount"),
            change_percent=detail.get("change_percent"),
            change_type=change_type,
            detected_at=now,
        )
        self.db.add(price_change)
        return price_change

    def listings_seen_by_task(self, task_id: int) -> list[Listing]:
        statement = (
            select(Listing)
            .join(ListingSnapshot, ListingSnapshot.listing_id == Listing.id)
            .where(ListingSnapshot.crawl_task_id == task_id)
            .where(Listing.current_status.in_(("active", "removed")))
            .distinct()
        )
        return list(self.db.scalars(statement))

    def snapshots(self, listing_id: int) -> list[ListingSnapshot]:
        return list(
            self.db.scalars(
                select(ListingSnapshot)
                .where(ListingSnapshot.listing_id == listing_id)
                .order_by(desc(ListingSnapshot.snapshot_at))
            )
        )

    def price_changes(self, listing_id: int) -> list[PriceChange]:
        return list(
            self.db.scalars(
                select(PriceChange).where(PriceChange.listing_id == listing_id).order_by(desc(PriceChange.detected_at))
            )
        )

    def events(self, listing_id: int) -> list[ListingEvent]:
        return list(
            self.db.scalars(
                select(ListingEvent).where(ListingEvent.listing_id == listing_id).order_by(desc(ListingEvent.created_at))
            )
        )

    def recent_events(self, limit: int = 20) -> list[ListingEvent]:
        return list(self.db.scalars(select(ListingEvent).order_by(desc(ListingEvent.created_at)).limit(limit)))

    def dashboard_counts(self, today_start: dt.datetime) -> dict[str, int]:
        active_count = self.db.scalar(select(func.count()).select_from(Listing).where(Listing.current_status == "active"))
        today_events = {
            event_type: self.db.scalar(
                select(func.count())
                .select_from(ListingEvent)
                .where(and_(ListingEvent.event_type == event_type, ListingEvent.created_at >= today_start))
            )
            for event_type in ("new_listing", "price_up", "price_down", "removed")
        }
        return {
            "active_count": active_count or 0,
            "today_new_count": today_events["new_listing"] or 0,
            "today_price_up_count": today_events["price_up"] or 0,
            "today_price_down_count": today_events["price_down"] or 0,
            "today_removed_count": today_events["removed"] or 0,
        }

    def _apply_filters(self, statement: Select[tuple[Listing]], filters: dict[str, Any]) -> Select[tuple[Listing]]:
        if filters.get("source"):
            statement = statement.where(Listing.source == filters["source"])
        if filters.get("city"):
            statement = statement.where(Listing.city == filters["city"])
        if filters.get("district"):
            statement = statement.where(Listing.district == filters["district"])
        if filters.get("community"):
            statement = statement.where(Listing.community.like(f"%{filters['community']}%"))
        if filters.get("keyword"):
            statement = statement.where(Listing.title.like(f"%{filters['keyword']}%"))
        if filters.get("status"):
            statement = statement.where(Listing.current_status == filters["status"])
        if filters.get("min_total_price") is not None:
            statement = statement.where(Listing.current_total_price >= filters["min_total_price"])
        if filters.get("max_total_price") is not None:
            statement = statement.where(Listing.current_total_price <= filters["max_total_price"])
        if filters.get("min_unit_price") is not None:
            statement = statement.where(Listing.current_unit_price >= filters["min_unit_price"])
        if filters.get("max_unit_price") is not None:
            statement = statement.where(Listing.current_unit_price <= filters["max_unit_price"])
        if filters.get("min_area") is not None:
            statement = statement.where(Listing.area >= filters["min_area"])
        if filters.get("max_area") is not None:
            statement = statement.where(Listing.area <= filters["max_area"])
        if filters.get("layout"):
            statement = statement.where(Listing.layout == filters["layout"])
        return statement


class CrawlRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        task_id: int,
        source: str,
        started_at: dt.datetime,
        finished_at: dt.datetime,
        status: str,
        stats: dict[str, Any],
        error_message: str | None = None,
    ) -> CrawlRun:
        run = CrawlRun(
            crawl_task_id=task_id,
            source=source,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            stats_json=stats,
            error_message=error_message,
        )
        self.db.add(run)
        self.db.flush()
        return run
