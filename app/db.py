"""DB 세션 관리. DATABASE_URL(Postgres 등)이 있으면 그걸 쓰고, 없으면 로컬 SQLite."""
from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATA_DIR, DB_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL:
    # Render/Heroku 스타일 postgres:// 를 SQLAlchemy 형식으로 보정
    url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)
else:
    DATA_DIR.mkdir(exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    from app import models  # noqa: F401 — 테이블 정의 로드

    models.Base.metadata.create_all(engine)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
