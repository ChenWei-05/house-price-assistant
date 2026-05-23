from __future__ import annotations

import datetime as dt
import logging
import urllib.parse

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.storage.database import get_session
from app.storage.repositories import CrawlTaskRepository, ListingRepository
from app.services.crawl_service import CrawlService


logger = logging.getLogger(__name__)


router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_session)):
    repository = ListingRepository(db)
    today_start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "summary": repository.dashboard_counts(today_start),
            "events": repository.recent_events(limit=10),
        },
    )


@router.get("/tasks")
def tasks(request: Request, db: Session = Depends(get_session)):
    return templates.TemplateResponse(
        "tasks.html",
        {
            "request": request,
            "tasks": CrawlTaskRepository(db).list(),
            "message": request.query_params.get("message"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/tasks")
async def create_task(request: Request, db: Session = Depends(get_session)):
    form = _parse_urlencoded_form(await request.body())
    filters_json = _build_xingfuli_filters(form)
    frequency_minutes = _safe_int(form.get("frequency_minutes"), default=360)

    CrawlTaskRepository(db).create(
        {
            "name": form.get("name") or "幸福里采集任务",
            "source": "xingfuli",
            "city": form.get("city") or "fz",
            "district": form.get("district") or None,
            "keyword": form.get("keyword") or None,
            "filters_json": filters_json,
            "frequency_minutes": frequency_minutes,
            "enabled": form.get("enabled") == "on",
        }
    )
    return _redirect_tasks(message="任务已创建")


@router.get("/tasks/{task_id}/edit")
def edit_task(task_id: int, request: Request, db: Session = Depends(get_session)):
    task = CrawlTaskRepository(db).get(task_id)
    if not task:
        return _redirect_tasks(error="任务不存在")
    return templates.TemplateResponse(
        "task_edit.html",
        {
            "request": request,
            "task": task,
            "xingfuli_url": task.filters_json.get("url", ""),
            "filter_params_url": task.filters_json.get("filter_params_url", ""),
        },
    )


@router.post("/tasks/{task_id}/edit")
async def update_task(task_id: int, request: Request, db: Session = Depends(get_session)):
    repository = CrawlTaskRepository(db)
    task = repository.get(task_id)
    if not task:
        return _redirect_tasks(error="任务不存在")

    form = _parse_urlencoded_form(await request.body())
    repository.update(
        task,
        {
            "name": form.get("name") or task.name,
            "city": form.get("city") or task.city,
            "district": form.get("district") or None,
            "keyword": form.get("keyword") or None,
            "filters_json": _build_xingfuli_filters(form),
            "frequency_minutes": _safe_int(form.get("frequency_minutes"), default=task.frequency_minutes),
            "enabled": form.get("enabled") == "on",
        },
    )
    return _redirect_tasks(message="任务已更新")


@router.post("/tasks/{task_id}/run")
def run_task(task_id: int, request: Request, db: Session = Depends(get_session)):
    logger.info(
        "Web immediate crawl action received task_id=%s method=%s path=%s client=%s",
        task_id,
        request.method,
        request.url.path,
        request.client.host if request.client else None,
    )
    try:
        run = CrawlService(db).run_task(task_id)
    except ValueError as exc:
        logger.exception("Web immediate crawl action rejected task_id=%s", task_id)
        return _redirect_tasks(error=str(exc))

    logger.info(
        "Web immediate crawl action completed task_id=%s run_id=%s status=%s stats=%s error=%s",
        task_id,
        run.id,
        run.status,
        run.stats_json,
        run.error_message,
    )
    if run.status == "failed":
        return _redirect_tasks(error=f"采集失败：{run.error_message or '未知错误'}")
    stats = run.stats_json
    return _redirect_tasks(
        message=(
            "采集完成："
            f"抓取 {stats.get('total_fetched', 0)} 条，"
            f"新增 {stats.get('new_count', 0)} 条，"
            f"降价 {stats.get('price_down_count', 0)} 条"
        )
    )


@router.get("/listings")
def listings(request: Request, db: Session = Depends(get_session)):
    repository = ListingRepository(db)
    sort_by = _normalize_listing_sort_by(request.query_params.get("sort_by"))
    sort_dir = _normalize_sort_dir(request.query_params.get("sort_dir"))
    filters = {
        "source": request.query_params.get("source"),
        "city": request.query_params.get("city"),
        "district": request.query_params.get("district"),
        "community": request.query_params.get("community"),
        "keyword": request.query_params.get("keyword"),
        "status": request.query_params.get("status"),
        "sort_by": sort_by,
        "sort_dir": sort_dir,
    }
    return templates.TemplateResponse(
        "listings.html",
        {
            "request": request,
            "listings": repository.list(filters, page=1, page_size=100),
            "filters": filters,
            "sort_links": {
                field: _listing_sort_url(request, field, sort_by, sort_dir)
                for field in ("area", "total_price", "unit_price")
            },
        },
    )


def _parse_urlencoded_form(body: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1].strip() for key, values in parsed.items()}


def _build_xingfuli_filters(form: dict[str, str]) -> dict[str, str]:
    filters_json: dict[str, str] = {}
    if form.get("xingfuli_url"):
        filters_json["url"] = form["xingfuli_url"]
    if form.get("filter_params_url"):
        filters_json["filter_params_url"] = form["filter_params_url"]
    if form.get("city"):
        filters_json["city_code"] = form["city"]
    return filters_json


def _safe_int(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _normalize_listing_sort_by(value: str | None) -> str | None:
    if value in {"area", "total_price", "unit_price"}:
        return value
    return None


def _normalize_sort_dir(value: str | None) -> str:
    if value == "asc":
        return "asc"
    return "desc"


def _listing_sort_url(request: Request, field: str, current_sort_by: str | None, current_sort_dir: str) -> str:
    next_sort_dir = "desc"
    if current_sort_by == field and current_sort_dir == "desc":
        next_sort_dir = "asc"

    params = dict(request.query_params)
    params["sort_by"] = field
    params["sort_dir"] = next_sort_dir
    return f"{request.url.path}?{urllib.parse.urlencode(params)}"


def _redirect_tasks(message: str | None = None, error: str | None = None) -> RedirectResponse:
    query = urllib.parse.urlencode(
        {
            key: value
            for key, value in {
                "message": message,
                "error": error,
            }.items()
            if value
        }
    )
    url = "/tasks"
    if query:
        url = f"{url}?{query}"
    return RedirectResponse(url=url, status_code=303)
