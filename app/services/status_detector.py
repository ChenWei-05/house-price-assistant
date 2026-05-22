from __future__ import annotations

import datetime as dt

from app.config import get_settings
from app.storage.models import Listing
from app.storage.repositories import ListingRepository


class StatusDetector:
    def mark_missing(
        self,
        repository: ListingRepository,
        task_id: int,
        seen_listing_ids: set[int],
        now: dt.datetime,
    ) -> int:
        removed_count = 0
        threshold = get_settings().crawl_missing_threshold

        for listing in repository.listings_seen_by_task(task_id):
            if listing.id in seen_listing_ids or listing.current_status != "active":
                continue

            listing.missing_count += 1
            if listing.missing_count >= threshold:
                self._mark_removed(repository, listing, now)
                removed_count += 1

        return removed_count

    def _mark_removed(self, repository: ListingRepository, listing: Listing, now: dt.datetime) -> None:
        listing.current_status = "removed"
        listing.removed_at = now
        repository.add_event(
            listing_id=listing.id,
            event_type="removed",
            detail={"missing_count": listing.missing_count},
            now=now,
        )

