from __future__ import annotations

from app.crawler.base import CrawledListing
from app.storage.models import Listing
from app.storage.repositories import ListingRepository


class ListingMatcher:
    def match(self, repository: ListingRepository, listing: CrawledListing) -> Listing | None:
        return repository.find_existing(listing)

