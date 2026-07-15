import os

# app.main 이 import 시점에 APP_PASSWORD 를 읽으므로 먼저 설정
os.environ["APP_PASSWORD"] = "testpw"
os.environ["DISABLE_SCHEDULER"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def test_root_is_public():
    assert client.get("/").status_code == 200


def test_collect_key_param_passes_auth():
    # 존재하지 않는 잡 이름 → 인증은 통과하되 실제 수집은 실행되지 않음
    r = client.get("/collect/nonexistent?key=testpw")
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_collect_wrong_key_rejected():
    assert client.get("/collect/listings?key=wrong").status_code == 401


def test_collect_missing_key_rejected():
    assert client.get("/collect/listings").status_code == 401
