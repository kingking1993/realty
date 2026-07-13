from datetime import date, datetime

from sqlalchemy import select

from app.models import Listing, Match, Transaction
from app.services.matcher import floor_band, parse_floor, run_matching


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


def test_transaction_not_reused_across_listings(session, complex_obj):
    session.add_all([
        _removed_listing(complex_obj.id, no="r1"),
        _removed_listing(complex_obj.id, no="r2"),
        _txn(complex_obj.id),
    ])
    session.flush()
    assert run_matching(session, now=datetime(2026, 7, 13)) == 1
    assert len(session.scalars(select(Match)).all()) == 1
