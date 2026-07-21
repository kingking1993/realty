from datetime import datetime

from sqlalchemy import select

from app.models import Listing, ListingEvent
from app.services.ingest import ingest_listing_snapshot, record_daily_counts


def _item(no: str, price: int = 100000, **kw) -> dict:
    return {
        "article_no": no, "trade_type": kw.get("trade_type", "매매"),
        "dong": kw.get("dong", "101동"), "floor_info": kw.get("floor_info", "10/25"),
        "area_exclusive": kw.get("area", 84.98), "price": price,
        "price_monthly": kw.get("monthly", 0), "description": "",
    }


def test_first_snapshot_creates_new(session, complex_obj):
    stats = ingest_listing_snapshot(session, complex_obj.id, [_item("a1"), _item("a2")])
    assert stats == {"new": 2, "price_changed": 0, "removed": 0, "unchanged": 0}
    assert session.scalars(select(Listing)).all().__len__() == 2


def test_identical_snapshot_is_idempotent(session, complex_obj):
    snap = [_item("a1"), _item("a2")]
    ingest_listing_snapshot(session, complex_obj.id, snap)
    stats = ingest_listing_snapshot(session, complex_obj.id, snap)
    assert stats["new"] == 0 and stats["removed"] == 0 and stats["price_changed"] == 0
    # NEW 이벤트 2건 외에 추가 이벤트가 없어야 함
    assert len(session.scalars(select(ListingEvent)).all()) == 2


def test_price_change_and_removal(session, complex_obj):
    t0 = datetime(2026, 7, 1, 10, 0)
    t1 = datetime(2026, 7, 2, 10, 0)
    ingest_listing_snapshot(session, complex_obj.id, [_item("a1", 100000), _item("a2")], now=t0)
    stats = ingest_listing_snapshot(session, complex_obj.id, [_item("a1", 95000)], now=t1)
    assert stats["price_changed"] == 1 and stats["removed"] == 1

    a1 = session.scalar(select(Listing).where(Listing.article_no == "a1"))
    assert a1.price == 95000 and a1.status == "active"
    a2 = session.scalar(select(Listing).where(Listing.article_no == "a2"))
    assert a2.status == "removed" and a2.removed_at == t1

    events = {e.event for e in session.scalars(select(ListingEvent))}
    assert events == {"NEW", "PRICE_CHANGED", "REMOVED"}


def test_relisted_article_becomes_active_again(session, complex_obj):
    t0, t1, t2 = datetime(2026, 7, 1), datetime(2026, 7, 2), datetime(2026, 7, 3)
    ingest_listing_snapshot(session, complex_obj.id, [_item("a1")], now=t0)
    ingest_listing_snapshot(session, complex_obj.id, [], now=t1)
    stats = ingest_listing_snapshot(session, complex_obj.id, [_item("a1")], now=t2)
    assert stats["new"] == 1
    a1 = session.scalar(select(Listing).where(Listing.article_no == "a1"))
    assert a1.status == "active" and a1.removed_at is None


def test_identical_transactions_in_batch_stored_once(session, complex_obj):
    from datetime import date

    from app.services.ingest import upsert_transactions

    t = {"apt_name": "테스트단지", "deal_date": date(2026, 6, 18), "price": 114000,
         "area_exclusive": 80.64, "floor": 14, "apt_dong": "", "is_canceled": False,
         "umd_nm": "등촌동"}
    added = upsert_transactions(session, complex_obj, [t, dict(t)])
    session.flush()
    assert added == 1


def test_umd_nm_filter(session, complex_obj):
    from datetime import date

    from app.services.ingest import _trade_belongs_to

    complex_obj.umd_nm = "등촌동"
    trade = {"apt_name": "테스트단지", "umd_nm": "방화동", "deal_date": date(2026, 6, 1),
             "price": 1, "area_exclusive": 1.0, "floor": 1}
    assert not _trade_belongs_to(trade, complex_obj)
    trade["umd_nm"] = "등촌동"
    assert _trade_belongs_to(trade, complex_obj)


def test_duplicate_article_links_stored_once(session, complex_obj):
    from app.services.ingest import upsert_articles

    a = {"source": "news", "keyword": "등촌부영", "title": "기사", "link": "http://x/1",
         "description": "", "pub_date": None}
    assert upsert_articles(session, complex_obj.id, [a, dict(a)]) == 1
    # 다음 키워드 검색에서 같은 링크가 또 와도 (별도 호출) 중복 저장 안 됨
    assert upsert_articles(session, complex_obj.id, [dict(a, keyword="등촌 부영")]) == 0


def test_article_relevance_filter():
    from app.services.jobs import _is_relevant

    assert _is_relevant({"title": "등촌 부영아파트 신고가", "description": ""}, "등촌 부영")
    assert not _is_relevant(
        {"title": "[산업소식] 효성 지원", "description": "등촌1복지관… 부영그룹 회장…"},
        "등촌부영",
    )
    # tokens 모드: 단어들이 떨어져 있어도 모두 등장하면 통과
    assert _is_relevant(
        {"title": "강서구 아파트값 상승, 부동산 시장 들썩", "description": ""},
        "강서구 부동산", mode="tokens",
    )
    assert not _is_relevant(
        {"title": "강서구 맛집 추천", "description": ""}, "강서구 부동산", mode="tokens",
    )


def test_blind_parse():
    from app.collectors.blind import parse_posts

    html = '''<div><a href="/kr/post/%EA%B0%95%EC%84%9C-abc123" class="tit">
        <b>강서구</b> 아파트 어때?</a>
        <a href="/kr/post/%EA%B0%95%EC%84%9C-abc123">강서구 아파트 어때?</a></div>'''
    posts = parse_posts(html)
    assert len(posts) == 1  # 중복 링크 제거
    assert posts[0]["title"] == "강서구 아파트 어때?"
    assert posts[0]["link"].startswith("https://www.teamblind.com/kr/post/")


def test_daily_counts(session, complex_obj):
    now = datetime(2026, 7, 13, 10, 0)
    ingest_listing_snapshot(session, complex_obj.id,
                            [_item("a1"), _item("a2", trade_type="전세")], now=now)
    record_daily_counts(session, complex_obj.id, now=now)
    from app.models import DailyCount
    rows = {(r.trade_type): r.count for r in session.scalars(select(DailyCount))}
    assert rows == {"매매": 1, "전세": 1, "월세": 0}


def test_daily_counts_uses_naver_counts_when_given(session, complex_obj):
    """네이버 공식 건수(counts)가 주어지면 우리 수집분과 무관하게 그 값을 저장한다
    — 대시보드가 네이버 웹의 '매물 N'과 정확히 일치하도록."""
    now = datetime(2026, 7, 13, 10, 0)
    ingest_listing_snapshot(session, complex_obj.id, [_item("a1"), _item("a2")], now=now)
    record_daily_counts(session, complex_obj.id, now=now,
                        counts={"매매": 13, "전세": 2, "월세": 0})
    from app.models import DailyCount
    rows = {r.trade_type: r.count for r in session.scalars(select(DailyCount))}
    assert rows == {"매매": 13, "전세": 2, "월세": 0}


def test_daily_counts_falls_back_to_collected(session, complex_obj):
    """counts가 없으면(건수 조회 실패) 우리가 수집한 active 매물 수로 대체."""
    now = datetime(2026, 7, 13, 10, 0)
    ingest_listing_snapshot(session, complex_obj.id, [_item("a1"), _item("a2")], now=now)
    record_daily_counts(session, complex_obj.id, now=now, counts=None)
    from app.models import DailyCount
    row = session.scalar(select(DailyCount).where(DailyCount.trade_type == "매매"))
    assert row.count == 2


def test_daily_counts_reflects_removal_with_autoflush_off(complex_obj_noautoflush):
    """운영 세션은 autoflush=False. 신규 매물 없이 소멸만 발생한 회차에서도
    record_daily_counts가 방금 REMOVED된 매물을 active로 잘못 세면 안 된다."""
    session, complex_obj = complex_obj_noautoflush
    t0 = datetime(2026, 7, 1, 10, 0)
    t1 = datetime(2026, 7, 2, 10, 0)
    ingest_listing_snapshot(session, complex_obj.id, [_item("a1"), _item("a2")], now=t0)
    session.flush()
    # a2만 사라진 스냅샷 — new=0 이라 ingest_listing_snapshot 내부에서 flush가 안 걸린다
    stats = ingest_listing_snapshot(session, complex_obj.id, [_item("a1")], now=t1)
    assert stats == {"new": 0, "price_changed": 0, "removed": 1, "unchanged": 1}

    record_daily_counts(session, complex_obj.id, now=t1)
    session.flush()  # autoflush=False라 조회 전 명시적으로 flush (session_scope의 commit과 동치)
    from app.models import DailyCount
    row = session.scalar(select(DailyCount).where(
        DailyCount.date == t1.date(), DailyCount.trade_type == "매매"))
    assert row.count == 1  # 2가 아니라 1이어야 함 (a2는 이미 removed)
