from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.storage.database import SessionLocal
from app.storage.repositories import CrawlTaskRepository
from app.services.crawl_service import CrawlService


def run_enabled_tasks() -> None:
    db = SessionLocal()
    try:
        task_repository = CrawlTaskRepository(db)
        service = CrawlService(db)
        for task in task_repository.enabled():
            service.run(task)
    finally:
        db.close()


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(run_enabled_tasks, "interval", minutes=5, id="run_enabled_crawl_tasks", replace_existing=True)
    return scheduler

