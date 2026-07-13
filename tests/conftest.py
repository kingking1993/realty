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
