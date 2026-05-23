from __future__ import annotations

import logging
import re
import urllib.parse

from app.config import get_settings
from app.crawler.base import BaseCrawler, CrawledListing
from app.crawler.parser import (
    decimal_from_text,
    extract_area,
    extract_community_from_title,
    extract_layout,
    extract_source_listing_id,
    first_match,
    strip_tags,
)


logger = logging.getLogger(__name__)


def normalize_xingfuli_filter_params_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("filter_params_url 不能为空。")

    parsed = urllib.parse.urlparse(value)
    if parsed.scheme and parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        filter_params = query.get("filter_params_url", [])
        if not filter_params:
            raise ValueError("传入的幸福里 URL 中没有 filter_params_url 参数。")
        return filter_params[0]

    if "%3D" in value or "%26" in value:
        return urllib.parse.unquote(value)
    return value


class XingfuliCrawler(BaseCrawler):
    source = "xingfuli"

    def fetch(self, task: object) -> list[CrawledListing]:
        import httpx

        settings = get_settings()
        url = self.build_url(task)
        logger.info(
            "Xingfuli crawler request url=%s task_id=%s city=%s district=%s",
            url,
            getattr(task, "id", None),
            getattr(task, "city", None),
            getattr(task, "district", None),
        )
        with httpx.Client(
            timeout=settings.crawl_request_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        ) as client:
            try:
                response = client.get(url)
                logger.info(
                    "Xingfuli crawler response status=%s request_url=%s final_url=%s",
                    response.status_code,
                    url,
                    response.url,
                )
                response.raise_for_status()
            except Exception:
                logger.exception("Xingfuli crawler request failed url=%s", url)
                raise
        listings = self.parse(response.text, str(response.url), task)
        logger.info("Xingfuli crawler parsed count=%s base_url=%s", len(listings), response.url)
        return listings

    def build_url(self, task: object) -> str:
        filters = getattr(task, "filters_json", {}) or {}
        # if filters.get("url"):
        #     url = str(filters["url"])
        #     logger.info("Xingfuli crawler using filters_json.url=%s", url)
        #     return url

        city_code = str(filters.get("city_code") or getattr(task, "city", "")).strip().lower()
        if not city_code:
            raise ValueError("幸福里采集任务需要 city 或 filters_json.city_code。")

        base_url = f"https://m.xflapp.com/ershoufang/{city_code}"
        filter_params_url = filters.get("filter_params_url")
        if filter_params_url:
            normalized_filter_params_url = normalize_xingfuli_filter_params_url(str(filter_params_url))
            query = urllib.parse.urlencode(
                {
                    "filter_params_url": normalized_filter_params_url,
                    "trigger_search": "1",
                }
            )
            url = f"{base_url}?{query}"
            logger.info(
                "Xingfuli crawler built filtered url=%s city_code=%s filter_params_url=%s normalized_filter_params_url=%s",
                url,
                city_code,
                filter_params_url,
                normalized_filter_params_url,
            )
            return url

        if getattr(task, "keyword", None):
            raise ValueError("幸福里关键词不能直接拼 URL，请在 filters_json.url 中传入浏览器复制的公开搜索页。")
        logger.info("Xingfuli crawler built base url=%s city_code=%s", base_url, city_code)
        return base_url

    def parse(self, html_text: str, base_url: str, task: object) -> list[CrawledListing]:
        card_pattern = (
            r"<a\b(?=[^>]*class=[\"'][^\"']*ttfe-f-house-card[^\"']*[\"'])"
            r"[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"
        )
        listings: list[CrawledListing] = []
        seen: set[str] = set()

        for match in re.finditer(card_pattern, html_text, flags=re.I | re.S):
            href, block = match.groups()
            url = urllib.parse.urljoin(base_url, href)
            source_listing_id = extract_source_listing_id(url)
            if not source_listing_id or source_listing_id in seen:
                continue
            seen.add(source_listing_id)

            title = first_match(
                (
                    r"<h2\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-title[^\"']*[\"'][^>]*>(.*?)</h2>",
                    r"<img\b[^>]*alt=[\"']([^\"']+)[\"']",
                ),
                block,
            )
            desc = first_match(
                (r"<h3\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-desc[^\"']*[\"'][^>]*>(.*?)</h3>",),
                block,
            )
            total_price_text = first_match(
                (r"<p\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-price-total[^\"']*[\"'][^>]*>(.*?)</p>",),
                block,
            )
            unit_price_text = first_match(
                (r"<p\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-price-per[^\"']*[\"'][^>]*>(.*?)</p>",),
                block,
            )
            tags = [
                strip_tags(tag)
                for tag in re.findall(
                    r"<p\b[^>]*class=[\"'][^\"']*p-inline-block[^\"']*[\"'][^>]*>(.*?)</p>",
                    block,
                    flags=re.I | re.S,
                )
            ]
            raw_text = " ".join(value for value in [title, desc, total_price_text, unit_price_text, *tags] if value)
            title = title or strip_tags(block)[:120]
            if not title:
                continue

            layout = extract_layout(title) or extract_layout(desc)
            area = extract_area(desc) or extract_area(raw_text)
            listing = CrawledListing(
                source=self.source,
                source_listing_id=source_listing_id,
                url=url,
                title=title,
                community=extract_community_from_title(title, layout),
                city=getattr(task, "city", None),
                district=getattr(task, "district", None),
                layout=layout,
                area=area,
                total_price=decimal_from_text(total_price_text),
                unit_price=decimal_from_text(unit_price_text),
                raw_data={
                    "title": title,
                    "description": desc,
                    "total_price_text": total_price_text,
                    "unit_price_text": unit_price_text,
                    "tags": tags,
                    "raw_text": raw_text[:1000],
                    "url": url,
                },
            )
            listings.append(listing)

        return listings
