from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api import dashboard, events, listings, tasks
from app.scheduler.jobs import build_scheduler
from app.storage.database import init_db
from app.web import routes as web_routes


logging.basicConfig(level=logging.INFO)
logging.getLogger("app").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    scheduler = build_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="House Price Assistant", version="0.1.0", lifespan=lifespan)

app.include_router(tasks.router)
app.include_router(listings.router)
app.include_router(events.router)
app.include_router(dashboard.router)
app.include_router(web_routes.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
