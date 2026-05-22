from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, ConfigDict


class ListingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    event_type: str
    event_detail_json: dict[str, Any]
    created_at: dt.datetime

