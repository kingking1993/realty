"""소멸(REMOVED)된 매매 매물 ↔ 실거래 매칭 추정.

실거래 신고는 계약 후 30일 이내이므로, 매물이 내려간 시점 전후로 계약일이
가까운 거래를 찾아 면적/층/동/가격으로 신뢰도를 매긴다. 어디까지나 추정이다.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Listing, Match, Transaction

logger = logging.getLogger(__name__)

LOOKBACK_DAYS = 90  # 이 기간 내 소멸 매물만 매칭 시도
DEAL_WINDOW_DAYS = 30  # 계약일이 removed_at ±30일
AREA_TOLERANCE = 0.5  # 전용면적 ±0.5㎡
PRICE_TOLERANCE = 0.10  # 호가 대비 ±10%면 가점


def parse_floor(floor_info: str) -> tuple[int | None, str | None, int | None]:
    """floor_info('12/25', '중/25', '고/15') → (층 숫자, 저/중/고 밴드, 총층)."""
    if not floor_info or "/" not in floor_info:
        return None, None, None
    level, _, total_s = floor_info.partition("/")
    level = level.strip()
    try:
        total = int(total_s.strip())
    except ValueError:
        total = None
    if level in ("저", "중", "고"):
        return None, level, total
    try:
        return int(level), None, total
    except ValueError:
        return None, None, total


def floor_band(floor: int, total: int) -> str:
    """실제 층수 → 저/중/고 밴드 (네이버 표기 기준 대략 3등분)."""
    if total <= 0:
        return "중"
    ratio = floor / total
    if ratio <= 1 / 3:
        return "저"
    if ratio <= 2 / 3:
        return "중"
    return "고"


def _score(listing: Listing, txn: Transaction) -> int | None:
    """매칭 점수. None이면 배제(모순되는 정보)."""
    score = 0

    floor_num, band, total = parse_floor(listing.floor_info)
    if floor_num is not None:
        if txn.floor == floor_num:
            score += 2
        else:
            return None  # 층 숫자가 명시돼 있는데 다르면 배제
    elif band is not None and total:
        if floor_band(txn.floor, total) == band:
            score += 1
        else:
            return None

    # 동(棟): 양쪽 다 있을 때만 비교. 표기 차이("101동" vs "101") 흡수
    if listing.dong and txn.apt_dong:
        a = listing.dong.replace("동", "").strip()
        b = txn.apt_dong.replace("동", "").strip()
        if a and b:
            if a == b:
                score += 2
            else:
                return None

    if listing.price and txn.price:
        if abs(txn.price - listing.price) <= listing.price * PRICE_TOLERANCE:
            score += 1

    return score


def _confidence(score: int) -> str:
    if score >= 4:
        return "HIGH"
    if score >= 2:
        return "MEDIUM"
    return "LOW"


def run_matching(session: Session, now: datetime | None = None) -> int:
    """미매칭 소멸 매매 매물에 대해 최적 실거래를 찾아 Match 기록. 신규 매칭 수 반환."""
    now = now or datetime.now()
    cutoff = now - timedelta(days=LOOKBACK_DAYS)

    matched_txn_ids = set(session.scalars(select(Match.transaction_id)))
    matched_listing_ids = set(session.scalars(select(Match.listing_id)))

    removed = list(session.scalars(
        select(Listing).where(
            Listing.status == "removed",
            Listing.trade_type == "매매",
            Listing.removed_at >= cutoff,
        ).order_by(Listing.removed_at)
    ))

    new_matches = 0
    for listing in removed:
        if listing.id in matched_listing_ids or listing.removed_at is None:
            continue
        window_start = (listing.removed_at - timedelta(days=DEAL_WINDOW_DAYS)).date()
        window_end = (listing.removed_at + timedelta(days=DEAL_WINDOW_DAYS)).date()
        candidates = session.scalars(
            select(Transaction).where(
                Transaction.complex_id == listing.complex_id,
                Transaction.is_canceled.is_(False),
                Transaction.deal_date >= window_start,
                Transaction.deal_date <= window_end,
                Transaction.area_exclusive >= listing.area_exclusive - AREA_TOLERANCE,
                Transaction.area_exclusive <= listing.area_exclusive + AREA_TOLERANCE,
            )
        )

        best: tuple[int, int, Transaction] | None = None  # (score, -price_diff, txn)
        for txn in candidates:
            if txn.id in matched_txn_ids:
                continue
            score = _score(listing, txn)
            if score is None:
                continue
            price_diff = abs(txn.price - listing.price) if listing.price else 0
            key = (score, -price_diff)
            if best is None or key > (best[0], best[1]):
                best = (score, -price_diff, txn)

        if best is not None:
            score, _, txn = best
            session.add(Match(
                listing_id=listing.id,
                transaction_id=txn.id,
                confidence=_confidence(score),
                matched_at=now,
            ))
            matched_txn_ids.add(txn.id)
            new_matches += 1

    if new_matches:
        logger.info("신규 매칭 %d건", new_matches)
    return new_matches
