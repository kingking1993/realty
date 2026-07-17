import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import Base, Complex


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


@pytest.fixture
def complex_obj(session):
    cx = Complex(name="테스트단지", naver_complex_no="99999", lawd_cd="11710",
                 apt_name_molit="테스트단지")
    session.add(cx)
    session.flush()
    return cx


@pytest.fixture
def complex_obj_noautoflush():
    """운영 세션(app/db.py)과 동일하게 autoflush=False로 만든 세션.

    기본 session 픽스처는 autoflush가 켜져 있어(SQLAlchemy 기본값), 운영에서만
    나타나는 autoflush=False 관련 버그를 재현하지 못한다.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine, autoflush=False)()
    cx = Complex(name="테스트단지", naver_complex_no="99999", lawd_cd="11710",
                 apt_name_molit="테스트단지")
    s.add(cx)
    s.flush()
    yield s, cx
    s.close()
