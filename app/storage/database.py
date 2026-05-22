from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _build_engine() -> Engine:
    settings = get_settings()
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        if settings.database_url.startswith("sqlite:///./"):
            db_path = Path(settings.database_url.removeprefix("sqlite:///"))
            db_path.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(settings.database_url, connect_args=connect_args)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.storage import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

