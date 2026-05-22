from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.tasks import CrawlRunRead, CrawlTaskCreate, CrawlTaskRead, CrawlTaskUpdate
from app.storage.database import get_session
from app.storage.repositories import CrawlTaskRepository
from app.services.crawl_service import CrawlService


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[CrawlTaskRead])
def list_tasks(db: Session = Depends(get_session)) -> list[object]:
    return CrawlTaskRepository(db).list()


@router.post("", response_model=CrawlTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(payload: CrawlTaskCreate, db: Session = Depends(get_session)) -> object:
    return CrawlTaskRepository(db).create(payload.model_dump())


@router.get("/{task_id}", response_model=CrawlTaskRead)
def get_task(task_id: int, db: Session = Depends(get_session)) -> object:
    task = CrawlTaskRepository(db).get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="采集任务不存在")
    return task


@router.put("/{task_id}", response_model=CrawlTaskRead)
def update_task(task_id: int, payload: CrawlTaskUpdate, db: Session = Depends(get_session)) -> object:
    repository = CrawlTaskRepository(db)
    task = repository.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="采集任务不存在")
    return repository.update(task, payload.model_dump(exclude_unset=True))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_session)) -> None:
    repository = CrawlTaskRepository(db)
    task = repository.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="采集任务不存在")
    repository.delete(task)


@router.post("/{task_id}/run", response_model=CrawlRunRead)
def run_task(task_id: int, db: Session = Depends(get_session)) -> object:
    try:
        run = CrawlService(db).run_task(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return run

