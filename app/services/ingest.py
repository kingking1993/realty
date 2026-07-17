"""수집 결과를 DB에 반영: 매물 diff, 매물 수 집계, 실거래/기사 upsert."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import ComplexConfig, load_complexes
from app.models import Article, Complex, DailyCount, Listing, ListingEvent, Transaction

logger = logging.getLogger(__name__)


def sync_complexes(session: Session) -> list[Complex]:
    """complexes.yaml의 단지를 DB에 upsert하고 목록 반환."""
    result = []
    for cfg in load_complexes():
        obj = session.scalar(select(Complex).where(Complex.naver_complex_no == cfg.naver_complex_no))
        if obj is None:
            obj = Complex(naver_complex_no=cfg.naver_complex_no)
            session.add(obj)
        obj.name = cfg.name
        obj.lawd_cd = cfg.lawd_cd
        obj.umd_nm = cfg.umd_nm
        obj.apt_name_molit = cfg.apt_name_molit
        session.flush()
        result.append(obj)
    return result


def ingest_listing_snapshot(
    session: Session, complex_id: int, snapshot: list[dict], now: datetime | None = None
) -> dict:
    """전체 매물 스냅샷을 기존 active 매물과 비교해 NEW/PRICE_CHANGED/REMOVED 반영.

    snapshot은 반드시 '완전한' 수집본이어야 한다. 부분 수집본을 넘기면
    남은 매물이 전부 REMOVED로 오판되므로, 수집 실패 시 호출하지 말 것.
    """
    now = now or datetime.now()
    active = {
        l.article_no: l
        for l in session.scalars(
            select(Listing).where(Listing.complex_id == complex_id, Listing.status == "active")
        )
    }
    snapshot_by_no = {a["article_no"]: a for a in snapshot if a.get("article_no")}

    stats = {"new": 0, "price_changed": 0, "removed": 0, "unchanged": 0}

    for article_no, item in snapshot_by_no.items():
        existing = active.get(article_no)
        if existing is None:
            # 과거 removed 매물이 같은 번호로 다시 나타나는 경우도 처리
            existing = session.scalar(select(Listing).where(Listing.article_no == article_no))
            if existing is not None:
                existing.status = "active"
                existing.removed_at = None
                existing.last_seen = now
                existing.price = item["price"]
                session.add(ListingEvent(listing_id=existing.id, event="NEW",
                                         new_price=item["price"], occurred_at=now))
                stats["new"] += 1
                continue
            listing = Listing(
                article_no=article_no,
                complex_id=complex_id,
                trade_type=item["trade_type"],
                dong=item["dong"],
                floor_info=item["floor_info"],
                area_exclusive=item["area_exclusive"],
                price=item["price"],
                price_monthly=item["price_monthly"],
                description=item.get("description", ""),
                first_seen=now,
                last_seen=now,
                status="active",
            )
            session.add(listing)
            session.flush()
            session.add(ListingEvent(listing_id=listing.id, event="NEW",
                                     new_price=item["price"], occurred_at=now))
            stats["new"] += 1
        else:
            existing.last_seen = now
            if existing.price != item["price"] or existing.price_monthly != item["price_monthly"]:
                session.add(ListingEvent(listing_id=existing.id, event="PRICE_CHANGED",
                                         old_price=existing.price, new_price=item["price"],
                                         occurred_at=now))
                existing.price = item["price"]
                existing.price_monthly = item["price_monthly"]
                stats["price_changed"] += 1
            else:
                stats["unchanged"] += 1

    for article_no, listing in active.items():
        if article_no not in snapshot_by_no:
            listing.status = "removed"
            listing.removed_at = now
            session.add(ListingEvent(listing_id=listing.id, event="REMOVED",
                                     old_price=listing.price, occurred_at=now))
            stats["removed"] += 1

    logger.info("complex %d diff: %s", complex_id, stats)
    return stats


def record_daily_counts(session: Session, complex_id: int, now: datetime | None = None) -> None:
    """현재 active 매물 수를 거래유형별로 오늘 날짜에 기록 (하루 여러 번이면 덮어씀)."""
    now = now or datetime.now()
    today = now.date()
    # 세션이 autoflush=False라서, 같은 잡에서 방금 REMOVED로 표시한 매물이
    # (신규 매물이 없어 flush를 안 거쳤다면) 이 SELECT엔 여전히 active로 잡힌다.
    session.flush()
    counts: dict[str, int] = {}
    for l in session.scalars(
        select(Listing).where(Listing.complex_id == complex_id, Listing.status == "active")
    ):
        counts[l.trade_type] = counts.get(l.trade_type, 0) + 1
    for trade_type in ("매매", "전세", "월세"):
        count = counts.get(trade_type, 0)
        row = session.scalar(
            select(DailyCount).where(
                DailyCount.complex_id == complex_id,
                DailyCount.date == today,
                DailyCount.trade_type == trade_type,
            )
        )
        if row is None:
            session.add(DailyCount(complex_id=complex_id, date=today,
                                   trade_type=trade_type, count=count))
        else:
            row.count = count


def _trade_belongs_to(trade: dict, complex_obj: Complex) -> bool:
    # "부영"처럼 흔한 이름은 같은 시군구의 다른 법정동에도 있을 수 있어 동 이름으로 먼저 거른다
    if complex_obj.umd_nm and trade.get("umd_nm", "") != complex_obj.umd_nm:
        return False
    apt_name = trade.get("apt_name", "")
    if complex_obj.apt_name_molit:
        return apt_name == complex_obj.apt_name_molit
    return bool(apt_name) and (apt_name in complex_obj.name or complex_obj.name in apt_name)


def upsert_transactions(session: Session, complex_obj: Complex, trades: list[dict]) -> int:
    """시군구 전체 거래 목록에서 이 단지 것만 골라 upsert. 신규 건수 반환."""
    added = 0
    unmatched_names: set[str] = set()
    # 같은 날·같은 가격·같은 층·동 미공개인 거래가 실제로 2건 있을 수 있으나,
    # 자연키로 구분이 불가능하므로 1건으로 저장한다 (배치 내 중복 커밋 충돌 방지)
    seen_keys: set[tuple] = set()
    for t in trades:
        if not _trade_belongs_to(t, complex_obj):
            unmatched_names.add(t.get("apt_name", ""))
            continue
        key = (t["deal_date"], t["price"], t["area_exclusive"], t["floor"])
        if key in seen_keys:
            continue
        seen_keys.add(key)
        existing = session.scalar(
            select(Transaction).where(
                Transaction.complex_id == complex_obj.id,
                Transaction.deal_date == t["deal_date"],
                Transaction.price == t["price"],
                Transaction.area_exclusive == t["area_exclusive"],
                Transaction.floor == t["floor"],
            )
        )
        if existing is None:
            session.add(Transaction(
                complex_id=complex_obj.id,
                deal_date=t["deal_date"],
                price=t["price"],
                area_exclusive=t["area_exclusive"],
                floor=t["floor"],
                apt_dong=t.get("apt_dong", ""),
                is_canceled=t.get("is_canceled", False),
            ))
            added += 1
        else:
            # 동 정보(등기 후 공개)와 해제 여부는 나중에 갱신될 수 있음
            if t.get("apt_dong") and not existing.apt_dong:
                existing.apt_dong = t["apt_dong"]
            existing.is_canceled = t.get("is_canceled", False)
    return added


def filter_new_articles(session: Session, items: list[dict]) -> list[dict]:
    """DB에 없는 링크의 항목만 반환 (작성일 조회 등 비싼 후처리 전 선별용)."""
    links = [i["link"] for i in items if i.get("link")]
    if not links:
        return []
    existing = set(session.scalars(select(Article.link).where(Article.link.in_(links))))
    return [i for i in items if i.get("link") and i["link"] not in existing]


def upsert_articles(session: Session, complex_id: int, items: list[dict],
                    topic: str = "complex", now: datetime | None = None) -> int:
    """뉴스/카페 글 저장 (link 기준 중복 제거). 신규 건수 반환."""
    now = now or datetime.now()
    added = 0
    seen_links: set[str] = set()  # 같은 응답 안의 중복 + autoflush=False 대비
    for item in items:
        if item["link"] in seen_links:
            continue
        seen_links.add(item["link"])
        if session.scalar(select(Article).where(Article.link == item["link"])):
            continue
        session.add(Article(
            source=item["source"],
            complex_id=complex_id,
            keyword=item.get("keyword", ""),
            topic=topic,
            title=item["title"],
            link=item["link"],
            description=item.get("description", ""),
            pub_date=item.get("pub_date"),
            fetched_at=now,
        ))
        added += 1
    # 세션이 autoflush=False 라서, 같은 잡에서 다음 키워드 검색 결과가
    # 방금 추가한 link 를 조회로 볼 수 있도록 즉시 flush
    session.flush()
    return added
