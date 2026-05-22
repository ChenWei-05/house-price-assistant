#!/usr/bin/env python3
"""
房产网站采集连通性测试工具。

用途：
- 检查目标搜索页是否允许当前 User-Agent 访问。
- 低频请求单个公开页面。
- 尝试解析页面标题和房源候选信息。
- 保存原始 HTML 与结构化 JSON，便于后续开发正式采集器。

本工具不包含验证码绕过、登录绕过、代理池或反爬规避逻辑。
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_USER_AGENT = "HousePriceAssistantCrawlerProbe/0.1"
DEFAULT_OUTPUT_DIR = Path("data/crawl_tests")


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    charset: str
    html_text: str


@dataclass
class ListingCandidate:
    title: str
    url: str | None = None
    total_price: str | None = None
    unit_price: str | None = None
    community: str | None = None
    area: str | None = None
    layout: str | None = None
    raw_text: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="低频、合规的房产网站采集连通性测试工具。"
    )
    parser.add_argument(
        "--source",
        choices=("beike", "xingfuli", "custom"),
        default="custom",
        help="数据源类型。beike 支持根据 city-code + keyword 生成测试 URL；其他来源建议传 --url。",
    )
    parser.add_argument(
        "--url",
        help="目标公开搜索页 URL。建议从浏览器复制搜索结果页地址。",
    )
    parser.add_argument(
        "--city-code",
        default="fz",
        help="城市代码。贝壳使用子域名前缀，如 bj、sh、hz；幸福里使用路径代码，如 bj、fz。",
    )
    parser.add_argument(
        "--keyword",
        help="搜索关键词。贝壳可直接生成 URL；幸福里关键词需复制搜索页 URL 或传 --filter-params-url。",
    )
    parser.add_argument(
        "--filter-params-url",
        help="幸福里搜索页里的 filter_params_url 参数，可传已编码或已解码的值。",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="请求使用的 User-Agent。",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="请求超时时间，单位秒。",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        help="最多输出的房源候选数量。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="保存 HTML 和 JSON 的目录。",
    )
    parser.add_argument(
        "--no-save-html",
        action="store_true",
        help="不保存原始 HTML。",
    )
    parser.add_argument(
        "--allow-unknown-robots",
        action="store_true",
        help="robots.txt 不可读取时仍继续请求。仅在你已人工确认允许访问时使用。",
    )
    return parser.parse_args()


def build_url(args: argparse.Namespace) -> str:
    if args.url:
        return args.url

    if args.source == "beike":
        if not args.keyword:
            raise ValueError("source=beike 且未传 --url 时，必须提供 --keyword。")
        keyword = urllib.parse.quote(args.keyword.strip())
        city_code = args.city_code.strip().lower()
        return f"https://{city_code}.ke.com/ershoufang/rs{keyword}/"

    if args.source == "xingfuli":
        return build_xingfuli_url(args)

    raise ValueError("该 source 暂未内置 URL 规则，请传入 --url。")


def build_xingfuli_url(args: argparse.Namespace) -> str:
    city_code = args.city_code.strip().lower()
    if not city_code:
        raise ValueError("source=xingfuli 时必须提供 --city-code，例如 fz、bj。")

    base_url = f"https://m.xflapp.com/ershoufang/{city_code}"
    if args.filter_params_url:
        filter_params_url = normalize_xingfuli_filter_params_url(args.filter_params_url)
        query = urllib.parse.urlencode(
            {
                "filter_params_url": filter_params_url,
                "trigger_search": "1",
            }
        )
        return f"{base_url}?{query}"

    if args.keyword:
        raise ValueError(
            "幸福里的简单 keyword 参数不会影响服务端返回结果。请在浏览器搜索后复制完整 --url，"
            "或从 URL 中提取 filter_params_url 后传给 --filter-params-url。"
        )

    return base_url


def normalize_xingfuli_filter_params_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("--filter-params-url 不能为空。")

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


def robots_url_for(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))


def check_robots(
    url: str,
    user_agent: str,
    timeout: float,
    allow_unknown_robots: bool,
) -> tuple[bool, str]:
    robots_url = robots_url_for(url)
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)

    try:
        request = urllib.request.Request(
            robots_url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/plain,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace").splitlines()
        parser.parse(body)
    except Exception as exc:  # noqa: BLE001 - CLI 工具需要把异常转成可读结果
        if allow_unknown_robots:
            return True, f"robots.txt 不可读取，已按参数继续：{exc}"
        return False, f"robots.txt 不可读取，已停止请求：{exc}"

    allowed = parser.can_fetch(user_agent, url)
    if allowed:
        return True, f"robots.txt 允许访问：{robots_url}"
    return False, f"robots.txt 不允许当前 User-Agent 访问该 URL：{robots_url}"


def fetch_url(url: str, user_agent: str, timeout: float) -> FetchResult:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip",
        },
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw_body = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            raw_body = gzip.decompress(raw_body)

        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        html_text = raw_body.decode(charset, errors="replace")

        return FetchResult(
            requested_url=url,
            final_url=response.geturl(),
            status_code=response.status,
            content_type=content_type,
            charset=charset,
            html_text=html_text,
        )


def strip_tags(value: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def absolutize_url(base_url: str, maybe_url: str | None) -> str | None:
    if not maybe_url:
        return None
    cleaned = html.unescape(maybe_url.strip())
    if cleaned.startswith(("javascript:", "#")):
        return None
    return urllib.parse.urljoin(base_url, cleaned)


def first_match(patterns: Iterable[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            return strip_tags(match.group(1))
    return None


def extract_title(html_text: str) -> str | None:
    return first_match((r"<title[^>]*>(.*?)</title>",), html_text)


def split_blocks_by_class(html_text: str, class_keywords: Iterable[str]) -> list[str]:
    blocks: list[str] = []
    for keyword in class_keywords:
        pattern = rf"<li\b[^>]*class=[\"'][^\"']*{re.escape(keyword)}[^\"']*[\"'][^>]*>.*?</li>"
        blocks.extend(re.findall(pattern, html_text, flags=re.I | re.S))
    return blocks


def parse_beike(html_text: str, base_url: str, max_candidates: int) -> list[ListingCandidate]:
    blocks = split_blocks_by_class(html_text, ("clear", "LOGCLICKDATA"))
    candidates: list[ListingCandidate] = []

    for block in blocks:
        if len(candidates) >= max_candidates:
            break

        if "totalPrice" not in block and "unitPrice" not in block and "ershoufang" not in block:
            continue

        title = first_match(
            (
                r"<div\b[^>]*class=[\"'][^\"']*title[^\"']*[\"'][^>]*>.*?<a\b[^>]*>(.*?)</a>",
                r"<a\b[^>]*class=[\"'][^\"']*title[^\"']*[\"'][^>]*>(.*?)</a>",
                r"<a\b[^>]*>(.*?)</a>",
            ),
            block,
        )
        href = first_match((r"<a\b[^>]*href=[\"']([^\"']+)[\"']",), block)
        total_price = first_match(
            (
                r"<div\b[^>]*class=[\"'][^\"']*totalPrice[^\"']*[\"'][^>]*>.*?<span[^>]*>(.*?)</span>",
                r"([0-9]+(?:\.[0-9]+)?)\s*万",
            ),
            block,
        )
        unit_price = first_match(
            (
                r"<div\b[^>]*class=[\"'][^\"']*unitPrice[^\"']*[\"'][^>]*>(.*?)</div>",
                r"单价\s*([0-9,]+)\s*元",
            ),
            block,
        )
        house_info = first_match(
            (r"<div\b[^>]*class=[\"'][^\"']*houseInfo[^\"']*[\"'][^>]*>(.*?)</div>",),
            block,
        )
        position_info = first_match(
            (r"<div\b[^>]*class=[\"'][^\"']*positionInfo[^\"']*[\"'][^>]*>(.*?)</div>",),
            block,
        )

        raw_text = strip_tags(block)
        if not title and not raw_text:
            continue

        layout, area = parse_layout_area(house_info or raw_text)
        candidates.append(
            ListingCandidate(
                title=title or raw_text[:80],
                url=absolutize_url(base_url, href),
                total_price=normalize_price_text(total_price),
                unit_price=normalize_price_text(unit_price),
                community=position_info,
                area=area,
                layout=layout,
                raw_text=raw_text[:500],
            )
        )

    return deduplicate_candidates(candidates)[:max_candidates]


def parse_xingfuli(html_text: str, base_url: str, max_candidates: int) -> list[ListingCandidate]:
    card_pattern = (
        r"<a\b(?=[^>]*class=[\"'][^\"']*ttfe-f-house-card[^\"']*[\"'])"
        r"[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"
    )
    candidates: list[ListingCandidate] = []

    for match in re.finditer(card_pattern, html_text, flags=re.I | re.S):
        if len(candidates) >= max_candidates:
            break

        href, block = match.groups()
        title = first_match(
            (
                r"<h2\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-title[^\"']*[\"'][^>]*>(.*?)</h2>",
                r"<img\b[^>]*alt=[\"']([^\"']+)[\"']",
            ),
            block,
        )
        desc = first_match(
            (
                r"<h3\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-desc[^\"']*[\"'][^>]*>(.*?)</h3>",
            ),
            block,
        )
        total_price = first_match(
            (
                r"<p\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-price-total[^\"']*[\"'][^>]*>(.*?)</p>",
            ),
            block,
        )
        unit_price = first_match(
            (
                r"<p\b[^>]*class=[\"'][^\"']*ttfe-f-house-card-info-price-per[^\"']*[\"'][^>]*>(.*?)</p>",
            ),
            block,
        )
        tags = re.findall(
            r"<p\b[^>]*class=[\"'][^\"']*p-inline-block[^\"']*[\"'][^>]*>(.*?)</p>",
            block,
            flags=re.I | re.S,
        )
        raw_text_parts = [value for value in (title, desc, total_price, unit_price) if value]
        raw_text_parts.extend(strip_tags(tag) for tag in tags)
        raw_text = " ".join(raw_text_parts)

        if not title:
            title = strip_tags(block)[:120]
        if not title:
            continue

        layout = extract_layout(title)
        area = extract_area(desc or raw_text)
        community = extract_community_from_xingfuli_title(title, layout)

        candidates.append(
            ListingCandidate(
                title=title,
                url=absolutize_url(base_url, href),
                total_price=normalize_price_text(total_price),
                unit_price=normalize_price_text(unit_price),
                community=community,
                area=area,
                layout=layout,
                raw_text=raw_text[:500],
            )
        )

    return deduplicate_candidates(candidates)[:max_candidates]


def parse_generic(html_text: str, base_url: str, max_candidates: int) -> list[ListingCandidate]:
    candidates: list[ListingCandidate] = []
    anchor_pattern = r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>"

    for match in re.finditer(anchor_pattern, html_text, flags=re.I | re.S):
        if len(candidates) >= max_candidates * 3:
            break

        href, anchor_html = match.groups()
        url = absolutize_url(base_url, href)
        title = strip_tags(anchor_html)
        if not url or len(title) < 4:
            continue

        searchable = f"{url} {title}"
        if not re.search(r"ershoufang|二手房|house|listing|fang|zufang|xiaoqu", searchable, re.I):
            continue

        start = max(0, match.start() - 800)
        end = min(len(html_text), match.end() + 1200)
        context = html_text[start:end]
        raw_text = strip_tags(context)
        total_price = first_match((r"([0-9]+(?:\.[0-9]+)?)\s*万",), raw_text)
        unit_price = first_match((r"单价\s*([0-9,]+)\s*元", r"([0-9,]+)\s*元/平"), raw_text)
        layout, area = parse_layout_area(raw_text)

        candidates.append(
            ListingCandidate(
                title=title[:120],
                url=url,
                total_price=normalize_price_text(total_price),
                unit_price=normalize_price_text(unit_price),
                area=area,
                layout=layout,
                raw_text=raw_text[:500],
            )
        )

    return deduplicate_candidates(candidates)[:max_candidates]


def parse_layout_area(text: str) -> tuple[str | None, str | None]:
    return extract_layout(text), extract_area(text)


def extract_layout(text: str | None) -> str | None:
    if not text:
        return None
    return first_match((r"([一二三四五六七八九十0-9]+室[一二三四五六七八九十0-9]+厅)",), text)


def extract_area(text: str | None) -> str | None:
    if not text:
        return None
    return first_match((r"([0-9]+(?:\.[0-9]+)?\s*(?:平|平米|㎡|m²|平方米))",), text)


def extract_community_from_xingfuli_title(title: str, layout: str | None) -> str | None:
    if not title:
        return None

    community = title.strip()
    if layout and community.startswith(layout):
        community = community[len(layout) :].strip()
    elif layout and layout in community:
        community = community.split(layout, 1)[0].strip()

    return community or None


def normalize_price_text(value: str | None) -> str | None:
    if not value:
        return None
    return re.sub(r"\s+", " ", value).strip()


def deduplicate_candidates(candidates: list[ListingCandidate]) -> list[ListingCandidate]:
    seen: set[tuple[str | None, str]] = set()
    result: list[ListingCandidate] = []
    for candidate in candidates:
        key = (candidate.url, candidate.title)
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def parse_listings(source: str, html_text: str, base_url: str, max_candidates: int) -> list[ListingCandidate]:
    if source == "beike":
        beike_candidates = parse_beike(html_text, base_url, max_candidates)
        if beike_candidates:
            return beike_candidates
    if source == "xingfuli":
        xingfuli_candidates = parse_xingfuli(html_text, base_url, max_candidates)
        if xingfuli_candidates:
            return xingfuli_candidates
    return parse_generic(html_text, base_url, max_candidates)


def safe_filename_part(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return value.strip("_")[:80] or "page"


def build_source_metadata(source: str, url: str) -> dict[str, object]:
    if source != "xingfuli":
        return {}

    parsed = urllib.parse.urlparse(url)
    path_match = re.search(r"/ershoufang/([^/?#]+)", parsed.path)
    query = urllib.parse.parse_qs(parsed.query)
    filter_params_values = query.get("filter_params_url", [])

    metadata: dict[str, object] = {
        "city_code": path_match.group(1) if path_match else None,
        "filter_params_url": filter_params_values[0] if filter_params_values else None,
    }

    if filter_params_values:
        nested_query = urllib.parse.parse_qs(filter_params_values[0])
        metadata["filter_params"] = {
            key: values[0] if len(values) == 1 else values
            for key, values in nested_query.items()
        }

    return metadata


def save_outputs(
    output_dir: Path,
    source: str,
    fetch_result: FetchResult,
    page_title: str | None,
    candidates: list[ListingCandidate],
    save_html: bool,
) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    domain = urllib.parse.urlparse(fetch_result.final_url).netloc
    stem = f"{timestamp}_{source}_{safe_filename_part(domain)}"

    html_path: Path | None = None
    if save_html:
        html_path = output_dir / f"{stem}.html"
        html_path.write_text(fetch_result.html_text, encoding="utf-8")

    json_path = output_dir / f"{stem}.json"
    payload = {
        "requested_url": fetch_result.requested_url,
        "final_url": fetch_result.final_url,
        "status_code": fetch_result.status_code,
        "content_type": fetch_result.content_type,
        "charset": fetch_result.charset,
        "title": page_title,
        "source_metadata": build_source_metadata(source, fetch_result.final_url),
        "candidates_count": len(candidates),
        "candidates": [asdict(candidate) for candidate in candidates],
        "saved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return json_path, html_path


def print_summary(
    fetch_result: FetchResult,
    page_title: str | None,
    candidates: list[ListingCandidate],
    json_path: Path,
    html_path: Path | None,
) -> None:
    print("采集连通性测试完成")
    print(f"- 请求 URL：{fetch_result.requested_url}")
    print(f"- 最终 URL：{fetch_result.final_url}")
    print(f"- HTTP 状态：{fetch_result.status_code}")
    print(f"- 内容类型：{fetch_result.content_type or '未知'}")
    print(f"- 页面标题：{page_title or '未解析到'}")
    print(f"- 候选房源：{len(candidates)} 条")
    print(f"- JSON 结果：{json_path}")
    if html_path:
        print(f"- HTML 快照：{html_path}")

    if candidates:
        print("\n候选房源预览：")
        for index, candidate in enumerate(candidates[:5], start=1):
            price = candidate.total_price or "价格未知"
            area = candidate.area or "面积未知"
            print(f"{index}. {candidate.title} | {price} | {area}")
            if candidate.url:
                print(f"   {candidate.url}")
    else:
        print("\n未解析到房源候选。可能原因：页面需要 JS 渲染、页面结构变化、关键词无结果，或访问被站点限制。")


def main() -> int:
    args = parse_args()

    try:
        url = build_url(args)
    except ValueError as exc:
        print(f"参数错误：{exc}", file=sys.stderr)
        return 2

    allowed, robots_message = check_robots(
        url=url,
        user_agent=args.user_agent,
        timeout=args.timeout,
        allow_unknown_robots=args.allow_unknown_robots,
    )
    print(robots_message)
    if not allowed:
        return 3

    try:
        fetch_result = fetch_url(url, args.user_agent, args.timeout)
    except urllib.error.HTTPError as exc:
        print(f"请求失败：HTTP {exc.code} {exc.reason}", file=sys.stderr)
        return 4
    except urllib.error.URLError as exc:
        print(f"请求失败：{exc.reason}", file=sys.stderr)
        return 4
    except TimeoutError:
        print("请求失败：连接超时", file=sys.stderr)
        return 4

    page_title = extract_title(fetch_result.html_text)
    candidates = parse_listings(
        source=args.source,
        html_text=fetch_result.html_text,
        base_url=fetch_result.final_url,
        max_candidates=args.max_candidates,
    )
    json_path, html_path = save_outputs(
        output_dir=args.output_dir,
        source=args.source,
        fetch_result=fetch_result,
        page_title=page_title,
        candidates=candidates,
        save_html=not args.no_save_html,
    )
    print_summary(fetch_result, page_title, candidates, json_path, html_path)
    return 0

# python tools/crawl_probe.py --source xingfuli --city-code fz --filter-params-url "neighborhood_id[]=6622474939549090055"
# 6631320275243761933

if __name__ == "__main__":
    raise SystemExit(main())
