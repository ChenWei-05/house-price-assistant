from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class CrawledListing:
    source: str
    source_listing_id: str
    url: str
    title: str
    community: str | None = None
    city: str | None = None
    district: str | None = None
    business_area: str | None = None
    address: str | None = None
    layout: str | None = None
    area: Decimal | None = None
    floor: str | None = None
    total_floor: int | None = None
    orientation: str | None = None
    build_year: int | None = None
    decoration: str | None = None
    has_elevator: bool | None = None
    total_price: Decimal | None = None
    unit_price: Decimal | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)


class BaseCrawler(ABC):
    source: str

    @abstractmethod
    def fetch(self, task: Any) -> list[CrawledListing]:
        """Fetch and normalize listings for a crawl task."""

