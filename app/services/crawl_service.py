from __future__ import annotations

import datetime as dt
import logging
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.crawler.registry import crawler_registry
from app.storage.models import CrawlRun, CrawlTask, utc_now
from app.storage.repositories import CrawlRunRepository, CrawlTaskRepository, ListingRepository
from app.services.listing_matcher import ListingMatcher
from app.services.price_tracker import PriceTracker
from app.services.status_detector import StatusDetector


logger = logging.getLogger(__name__)


@dataclass
class CrawlStats:
    total_fetched: int = 0
    new_count: int = 0
    price_up_count: int = 0
    price_down_count: int = 0
    removed_count: int = 0
    reappeared_count: int = 0
    unchanged_count: int = 0
    failed_count: int = 0


class CrawlService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.tasks = CrawlTaskRepository(db)
        self.listings = ListingRepository(db)
        self.runs = CrawlRunRepository(db)
        self.matcher = ListingMatcher()
        self.price_tracker = PriceTracker()
        self.status_detector = StatusDetector()

    def run_task(self, task_id: int) -> CrawlRun:
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"采集任务不存在：{task_id}")
        return self.run(task)

    def run(self, task: CrawlTask) -> CrawlRun:
        if task.source not in crawler_registry:
            raise ValueError(f"暂不支持的数据源：{task.source}")

        crawler = crawler_registry[task.source]
        started_at = utc_now()
        stats = CrawlStats()
        request_url: str | None = None
        try:
            logger.info(
                "Crawl task starting task_id=%s source=%s city=%s district=%s keyword=%s",
                task.id,
                task.source,
                task.city,
                task.district,
                task.keyword,
            )
            build_url = getattr(crawler, "build_url", None)
            if callable(build_url):
                request_url = build_url(task)
                logger.info(
                    "Crawl task built request url=%s task_id=%s source=%s",
                    request_url,
                    task.id,
                    task.source,
                )

            crawled_listings = crawler.fetch(task)
            stats.total_fetched = len(crawled_listings)
            logger.info(
                "Crawl task fetched task_id=%s source=%s request_url=%s total_fetched=%s",
                task.id,
                task.source,
                request_url,
                stats.total_fetched,
            )
            seen_listing_ids = self._persist_listings(task, crawled_listings, stats, started_at)
            stats.removed_count = self.status_detector.mark_missing(
                self.listings,
                task_id=task.id,
                seen_listing_ids=seen_listing_ids,
                now=started_at,
            )
            finished_at = utc_now()
            self._update_task_schedule(task, finished_at)
            run = self.runs.create(
                task_id=task.id,
                source=task.source,
                started_at=started_at,
                finished_at=finished_at,
                status="success",
                stats=asdict(stats),
            )
            self.db.commit()
            self.db.refresh(run)
            logger.info(
                "Crawl task succeeded task_id=%s run_id=%s source=%s request_url=%s stats=%s",
                task.id,
                run.id,
                task.source,
                request_url,
                asdict(stats),
            )
            return run
        except Exception as exc:
            logger.exception(
                "Crawl task failed task_id=%s source=%s request_url=%s",
                task.id,
                task.source,
                request_url,
            )
            self.db.rollback()
            finished_at = utc_now()
            run = self.runs.create(
                task_id=task.id,
                source=task.source,
                started_at=started_at,
                finished_at=finished_at,
                status="failed",
                stats=asdict(stats),
                error_message=str(exc),
            )
            self.db.commit()
            self.db.refresh(run)
            return run

    def _persist_listings(
        self,
        task: CrawlTask,
        crawled_listings: list[Any],
        stats: CrawlStats,
        now: dt.datetime,
    ) -> set[int]:
        seen_listing_ids: set[int] = set()

        for crawled in crawled_listings:
            existing = self.matcher.match(self.listings, crawled)
            if existing is None:
                listing = self.listings.create_from_crawled(crawled, now)
                self.listings.add_event(
                    listing_id=listing.id,
                    event_type="new_listing",
                    detail={"source_listing_id": crawled.source_listing_id, "url": crawled.url},
                    now=now,
                )
                stats.new_count += 1
            else:
                listing = existing
                if listing.current_status == "removed":
                    self.listings.add_event(
                        listing_id=listing.id,
                        event_type="reappeared",
                        detail={"url": crawled.url},
                        now=now,
                    )
                    stats.reappeared_count += 1

                price_event = self.price_tracker.detect(listing, crawled)
                if price_event:
                    event_type, detail = price_event
                    if event_type in ("price_up", "price_down"):
                        self.listings.add_price_change(
                            listing_id=listing.id,
                            change_type=event_type.removeprefix("price_"),
                            detail=detail,
                            now=now,
                        )
                        if event_type == "price_up":
                            stats.price_up_count += 1
                        else:
                            stats.price_down_count += 1
                    self.listings.add_event(listing_id=listing.id, event_type=event_type, detail=detail, now=now)
                else:
                    stats.unchanged_count += 1

                self.listings.update_from_crawled(listing, crawled, now)

            self.db.flush()
            seen_listing_ids.add(listing.id)
            self.listings.add_snapshot(listing.id, task.id, crawled, now)

        return seen_listing_ids

    def _update_task_schedule(self, task: CrawlTask, finished_at: dt.datetime) -> None:
        task.last_run_at = finished_at
        task.next_run_at = finished_at + dt.timedelta(minutes=task.frequency_minutes)
