from __future__ import annotations

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    active_count: int
    today_new_count: int
    today_price_up_count: int
    today_price_down_count: int
    today_removed_count: int

