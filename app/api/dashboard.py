from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.dashboard import DashboardSummary
from app.storage.database import get_session
from app.storage.repositories import ListingRepository


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_session)) -> dict[str, int]:
    today_start = dt.datetime.now(dt.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return ListingRepository(db).dashboard_counts(today_start)

