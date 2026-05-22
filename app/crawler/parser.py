from __future__ import annotations

import html
import re
from decimal import Decimal, InvalidOperation
from typing import Iterable


def strip_tags(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def first_match(patterns: Iterable[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return strip_tags(match.group(1))
    return None


def decimal_from_text(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = re.search(r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)", value)
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None


def extract_layout(text: str | None) -> str | None:
    if not text:
        return None
    return first_match((r"([一二三四五六七八九十0-9]+室[一二三四五六七八九十0-9]+厅)",), text)


def extract_area(text: str | None) -> Decimal | None:
    if not text:
        return None
    return decimal_from_text(first_match((r"([0-9]+(?:\.[0-9]+)?\s*(?:平|平米|㎡|m²|平方米))",), text))


def extract_source_listing_id(url: str) -> str | None:
    match = re.search(r"/ershoufang/[^/?#]*?-(\d+)\.html", url)
    if match:
        return match.group(1)
    match = re.search(r"(\d{12,})", url)
    if match:
        return match.group(1)
    return None


def extract_community_from_title(title: str, layout: str | None) -> str | None:
    community = title.strip()
    if layout and layout in community:
        community = community.split(layout, 1)[0].strip()
    return community or None

