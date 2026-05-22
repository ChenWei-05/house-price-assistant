from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.schemas.events import ListingEventRead
from app.storage.database import get_session
from app.storage.repositories import ListingRepository


router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/recent", response_model=list[ListingEventRead])
def recent_events(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_session),
) -> list[object]:
    return ListingRepository(db).recent_events(limit=limit)

