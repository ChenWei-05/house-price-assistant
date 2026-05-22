from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.crawler.base import CrawledListing
from app.storage.models import Listing


class PriceTracker:
    def detect(self, current: Listing, incoming: CrawledListing) -> tuple[str, dict[str, Any]] | None:
        old_total = current.current_total_price
        new_total = incoming.total_price
        old_unit = current.current_unit_price
        new_unit = incoming.unit_price

        if old_total is None or new_total is None:
            if old_unit != new_unit:
                return "info_changed", {
                    "old_unit_price": old_unit,
                    "new_unit_price": new_unit,
                }
            return None

        if old_total == new_total:
            if old_unit != new_unit:
                return "info_changed", {
                    "old_total_price": old_total,
                    "new_total_price": new_total,
                    "old_unit_price": old_unit,
                    "new_unit_price": new_unit,
                }
            return None

        change_amount = new_total - old_total
        change_percent = None
        if old_total != Decimal("0"):
            change_percent = (change_amount / old_total * Decimal("100")).quantize(Decimal("0.0001"))
        change_type = "price_up" if change_amount > 0 else "price_down"
        return change_type, {
            "old_total_price": old_total,
            "new_total_price": new_total,
            "old_unit_price": old_unit,
            "new_unit_price": new_unit,
            "change_amount": change_amount,
            "change_percent": change_percent,
        }

