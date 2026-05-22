from __future__ import annotations

from app.crawler.base import BaseCrawler
from app.crawler.xingfuli import XingfuliCrawler


crawler_registry: dict[str, BaseCrawler] = {
    "xingfuli": XingfuliCrawler(),
}

