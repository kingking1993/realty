"""로컬 SQLite → DATABASE_URL(Postgres) 데이터 이전.

테이블을 FK 의존성 순서로 복사하고 (ID 보존), Postgres 시퀀스를 재설정한다.
대상 DB에 이미 데이터가 있으면 중단한다 (덮어쓰기 방지).

사용법: python scripts/migrate_to_pg.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, func, select, text

from app.config import DB_PATH
from app.db import DATABASE_URL
from app.models import Base


def main() -> None:
    if not DATABASE_URL:
        print("DATABASE_URL이 설정되지 않았습니다 (.env 확인)")
        sys.exit(1)
    if not DB_PATH.exists():
        print(f"원본 SQLite가 없습니다: {DB_PATH}")
        sys.exit(1)

    src = create_engine(f"sqlite:///{DB_PATH}")
    dst = create_engine(DATABASE_URL.replace("postgres://", "postgresql://", 1),
                        pool_pre_ping=True)

    Base.metadata.create_all(dst)

    with dst.connect() as d:
        existing = d.execute(select(func.count()).select_from(
            Base.metadata.tables["listings"])).scalar()
        if existing:
            print(f"대상 DB에 이미 listings {existing}건이 있습니다 — 중단 (덮어쓰기 방지)")
            sys.exit(1)

    with src.connect() as s, dst.begin() as d:
        for table in Base.metadata.sorted_tables:
            rows = [dict(r._mapping) for r in s.execute(select(table))]
            if rows:
                d.execute(table.insert(), rows)
            if "id" in table.c:
                d.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 1) FROM {table.name}))"
                ))
            print(f"  {table.name}: {len(rows)}건")
    print("이전 완료")


if __name__ == "__main__":
    main()
