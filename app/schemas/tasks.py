from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CrawlTaskBase(BaseModel):
    name: str
    source: Literal["xingfuli"] = "xingfuli"
    city: str
    district: str | None = None
    keyword: str | None = None
    filters_json: dict[str, Any] = Field(default_factory=dict)
    frequency_minutes: int = 360
    enabled: bool = True


class CrawlTaskCreate(CrawlTaskBase):
    pass


class CrawlTaskUpdate(BaseModel):
    name: str | None = None
    city: str | None = None
    district: str | None = None
    keyword: str | None = None
    filters_json: dict[str, Any] | None = None
    frequency_minutes: int | None = None
    enabled: bool | None = None


class CrawlTaskRead(CrawlTaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_run_at: dt.datetime | None
    next_run_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime


class CrawlRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    crawl_task_id: int
    source: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    status: str
    stats_json: dict[str, Any]
    error_message: str | None

