from datetime import date, datetime

from sqlalchemy import select

from app.models import Listing, Match, Transaction
from app.services.matcher import find_relistings, floor_band, parse_floor, run_matching


def test_parse_floor():
    assert parse_floor("12/25") == (12, None, 25)
    assert parse_floor("중/25") == (None, "중", 25)
    assert parse_floor("고/15") == (None, "고", 15)
    assert parse_floor("") == (None, None, None)
    assert parse_floor("-") == (None, None, None)


def test_floor_band():
    assert floor_band(2, 25) == "저"
    assert floor_band(12, 25) == "중"
    assert floor_band(22, 25) == "고"


def _removed_listing(complex_id: int, **kw) -> Listing:
    return Listing(
        article_no=kw.get("no", "r1"), complex_id=complex_id,
        trade_type=kw.get("trade_type", "매매"), dong=kw.get("dong", "101동"),
        floor_info=kw.get("floor_info", "12/25"), area_exclusive=kw.get("area", 84.98),
        price=kw.get("price", 220000), price_monthly=0,
        first_seen=datetime(2026, 6, 1), last_seen=datetime(2026, 7, 1),
        status="removed", removed_at=kw.get("removed_at", datetime(2026, 7, 1)),
    )


def _txn(complex_id: int, **kw) -> Transaction:
    return Transaction(
        complex_id=complex_id, deal_date=kw.get("deal_date", date(2026, 6, 28)),
        price=kw.get("price", 218000), area_exclusive=kw.get("area", 84.98),
        floor=kw.get("floor", 12), apt_dong=kw.get("apt_dong", "101"),
        is_canceled=kw.get("is_canceled", False),
    )


def test_high_confidence_match(session, complex_obj):
    l = _removed_listing(complex_obj.id)
    t = _txn(complex_obj.id)
    session.add_all([l, t])
    session.flush()

    assert run_matching(session, now=datetime(2026, 7, 13)) == 1
    m = session.scalar(select(Match))
    assert m.listing_id == l.id and m.transaction_id == t.id
    assert m.confidence == "HIGH"  # 층 일치(+2) + 동 일치(+2) + 가격 근접(+1)


def test_floor_mismatch_excluded(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, floor_info="3/25"),
        _txn(complex_obj.id, floor=20),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 0


def test_dong_mismatch_excluded(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, dong="103동"),
        _txn(complex_obj.id, apt_dong="101"),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 0


def test_band_floor_matching(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, floor_info="중/25", dong=""),
        _txn(complex_obj.id, floor=12, apt_dong=""),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 1
    assert session.scalar(select(Match)).confidence == "MEDIUM"  # 밴드(+1) + 가격(+1)


def test_canceled_and_out_of_window_excluded(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id),
        _txn(complex_obj.id, is_canceled=True),
        _txn(complex_obj.id, deal_date=date(2026, 3, 1), price=219000),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 0


def test_jeonse_listing_not_matched(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, trade_type="전세"),
        _txn(complex_obj.id),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 0


def test_naver_rounded_area_still_matches_molit_exact_area(session, complex_obj):
    """네이버 area2(80.0)와 국토부 실거래 전용면적(80.64)의 0.64㎡ 차이는
    반올림 표기 차이일 뿐이므로 매칭되어야 한다."""
    session.add_all([
        _removed_listing(complex_obj.id, area=80.0, dong="", floor_info="중/15"),
        _txn(complex_obj.id, area=80.64, floor=8, apt_dong=""),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 1


def test_transaction_not_reused_across_listings(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, no="r1"),
        _removed_listing(complex_obj.id, no="r2"),
        _txn(complex_obj.id),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 1
    assert len(session.scalars(select(Match)).all()) == 1


def _active_listing(complex_id: int, **kw) -> Listing:
    return Listing(
        article_no=kw.get("no", "n1"), complex_id=complex_id,
        trade_type=kw.get("trade_type", "매매"), dong=kw.get("dong", "101동"),
        floor_info=kw.get("floor_info", "12/25"), area_exclusive=kw.get("area", 84.98),
        price=kw.get("price", 220000), price_monthly=0,
        first_seen=kw.get("first_seen", datetime(2026, 7, 5)),
        last_seen=kw.get("first_seen", datetime(2026, 7, 5)), status="active",
    )


def test_find_relistings_detects_same_unit_reappearance(session, complex_obj):
    """소멸 후 window 내 같은 세대가 다시 나오면 재등록으로 추정."""
    removed = _removed_listing(complex_obj.id, no="old", removed_at=datetime(2026, 7, 1))
    new = _active_listing(complex_obj.id, no="new", first_seen=datetime(2026, 7, 5))
    session.add_all([removed, new])
    session.flush()
    rel = find_relistings(session, now=datetime(2026, 7, 10))
    assert rel == {new.id: removed.id}


def test_find_relistings_ignores_out_of_window_and_other_units(session, complex_obj):
    removed = _removed_listing(complex_obj.id, no="old", removed_at=datetime(2026, 7, 1))
    too_late = _active_listing(complex_obj.id, no="late", first_seen=datetime(2026, 8, 1))
    other = _active_listing(complex_obj.id, no="other", dong="999동",
                            first_seen=datetime(2026, 7, 3))
    session.add_all([removed, too_late, other])
    session.flush()
    assert find_relistings(session, now=datetime(2026, 8, 5)) == {}


def test_relisted_weak_match_yields_to_relisting(session, complex_obj):
    """재등록 추정 매물에 붙은 '약한' 매칭(동 정보 없는 실거래)은, 이후 같은 세대가
    다시 등록되면 정리되고 더는 실거래로 매칭하지 않는다."""
    # 동/층 밴드만 있는 약한 매칭 조건 (실거래 apt_dong 없음)
    removed = _removed_listing(complex_obj.id, no="old", dong="", floor_info="중/25",
                               removed_at=datetime(2026, 7, 1))
    txn = _txn(complex_obj.id, deal_date=date(2026, 6, 28), apt_dong="", floor=12)
    session.add_all([removed, txn])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 2)) == 1  # 아직 재등록 없음 → 매칭
    assert len(session.scalars(select(Match)).all()) == 1

    session.add(_active_listing(complex_obj.id, no="new", dong="", floor_info="중/25",
                                first_seen=datetime(2026, 7, 6)))
    session.flush()
    run_matching(session, now=datetime(2026, 7, 10))
    assert len(session.scalars(select(Match)).all()) == 0  # 약한 매칭 정리, 재등록으로 남김


def test_strong_transaction_match_overrides_relisting(session, complex_obj):
    """재등록으로 추정되더라도, 실거래가 해당 동·층에 정확히 뜨면(강한 근거)
    재등록이 아니라 실제 거래로 보고 실거래 매칭을 유지한다."""
    removed = _removed_listing(complex_obj.id, no="old", dong="101동", floor_info="12/25",
                               removed_at=datetime(2026, 7, 1))
    txn = _txn(complex_obj.id, deal_date=date(2026, 6, 28), apt_dong="101", floor=12)
    same_unit_reappears = _active_listing(complex_obj.id, no="new", dong="101동",
                                          floor_info="12/25", first_seen=datetime(2026, 7, 6))
    session.add_all([removed, txn, same_unit_reappears])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 10)) == 1  # 강한 매칭 → 실거래로 인정
    m = session.scalar(select(Match))
    assert m.listing_id == removed.id and m.confidence == "HIGH"
