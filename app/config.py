from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    database_url: str = "sqlite:///./data/house_price.db"
    crawl_default_interval_minutes: int = 360
    crawl_request_timeout_seconds: float = 15.0
    crawl_max_pages_per_task: int = 1
    crawl_missing_threshold: int = 3
    user_agent: str = "HousePriceAssistant/0.1"
    supported_sources: tuple[str, ...] = ("xingfuli",)


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/house_price.db"),
        crawl_default_interval_minutes=_get_int("CRAWL_DEFAULT_INTERVAL_MINUTES", 360),
        crawl_request_timeout_seconds=_get_float("CRAWL_REQUEST_TIMEOUT_SECONDS", 15.0),
        crawl_max_pages_per_task=_get_int("CRAWL_MAX_PAGES_PER_TASK", 1),
        crawl_missing_threshold=_get_int("CRAWL_MISSING_THRESHOLD", 3),
        user_agent=os.getenv("USER_AGENT", "HousePriceAssistant/0.1"),
    )

