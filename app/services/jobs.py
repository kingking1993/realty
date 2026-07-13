"""수집 잡 오케스트레이션. 스케줄러(main.py)와 수동 실행(scripts/collect_now.py)이 공용."""
from __future__ import annotations

import logging
from datetime import datetime

from app.collectors import molit, naver_land, naver_search
from app.config import load_complexes
from app.db import session_scope
from app.models import CollectionLog
from app.services import ingest, matcher

logger = logging.getLogger(__name__)


def _is_relevant(item: dict, keyword: str) -> bool:
    """검색 키워드가 (공백 무시하고) 제목+본문에 붙어서 등장하는 기사만 통과.

    네이버 검색은 '등촌부영'으로 검색해도 '등촌'과 '부영그룹'이 따로 나오는
    기사까지 돌려주므로, 단지와 무관한 기사를 거른다.
    """
    text = (item.get("title", "") + " " + item.get("description", "")).replace(" ", "")
    return keyword.replace(" ", "") in text


def _log_run(session, job: str, started: datetime, ok: bool, detail: str) -> None:
    session.add(CollectionLog(job=job, started_at=started, finished_at=datetime.now(),
                              ok=ok, detail=detail))


def run_listings_job() -> str:
    """단지별 매물 스냅샷 수집 → diff → 매물 수 집계.

    단지 하나가 실패해도 나머지는 계속 진행하고, 실패한 단지는 diff를 건너뛴다.
    """
    started = datetime.now()
    lines: list[str] = []
    all_ok = True
    with session_scope() as session:
        complexes = ingest.sync_complexes(session)
        for cx in complexes:
            try:
                snapshot = naver_land.fetch_listings(cx.naver_complex_no)
            except naver_land.NaverLandError as e:
                all_ok = False
                lines.append(f"{cx.name}: 수집 실패 — {e} (diff 건너뜀)")
                logger.error("%s 매물 수집 실패: %s", cx.name, e)
                continue
            stats = ingest.ingest_listing_snapshot(session, cx.id, snapshot)
            ingest.record_daily_counts(session, cx.id)
            lines.append(
                f"{cx.name}: 총 {len(snapshot)}건 "
                f"(신규 {stats['new']}, 가격변동 {stats['price_changed']}, 소멸 {stats['removed']})"
            )
        detail = "\n".join(lines) or "등록된 단지 없음"
        _log_run(session, "listings", started, all_ok, detail)
    return detail


def run_transactions_job() -> str:
    """실거래가 수집(최근 3개월 재조회) → upsert → 소멸 매물 매칭."""
    started = datetime.now()
    lines: list[str] = []
    all_ok = True
    with session_scope() as session:
        complexes = ingest.sync_complexes(session)
        lawd_cds = sorted({cx.lawd_cd for cx in complexes})
        trades_by_lawd: dict[str, list[dict]] = {}
        for lawd_cd in lawd_cds:
            monthly: list[dict] = []
            try:
                for ymd in molit.recent_deal_ymds():
                    monthly.extend(molit.fetch_trades(lawd_cd, ymd))
                trades_by_lawd[lawd_cd] = monthly
            except molit.MolitError as e:
                all_ok = False
                lines.append(f"법정동 {lawd_cd}: 수집 실패 — {e}")
                logger.error("실거래 수집 실패 (%s): %s", lawd_cd, e)

        for cx in complexes:
            trades = trades_by_lawd.get(cx.lawd_cd)
            if trades is None:
                continue
            added = ingest.upsert_transactions(session, cx, trades)
            mine = [t for t in trades if ingest._trade_belongs_to(t, cx)]
            lines.append(f"{cx.name}: 거래 {len(mine)}건 확인, 신규 {added}건")
            if not mine and trades:
                names = sorted({t.get("apt_name", "") for t in trades})[:20]
                lines.append(
                    f"  ⚠ '{cx.apt_name_molit or cx.name}'와 일치하는 단지명이 없습니다. "
                    f"complexes.yaml의 apt_name_molit을 확인하세요. 이 지역 단지명 예: {', '.join(names)}"
                )

        matched = matcher.run_matching(session)
        lines.append(f"매칭: 신규 {matched}건")
        detail = "\n".join(lines) or "등록된 단지 없음"
        _log_run(session, "transactions", started, all_ok, detail)
    return detail


def run_articles_job() -> str:
    """단지별 키워드로 뉴스/카페 글 수집."""
    started = datetime.now()
    lines: list[str] = []
    all_ok = True
    with session_scope() as session:
        complexes = ingest.sync_complexes(session)
        cfg_by_no = {c.naver_complex_no: c for c in load_complexes()}
        for cx in complexes:
            cfg = cfg_by_no.get(cx.naver_complex_no)
            keywords = cfg.keywords if cfg else [cx.name]
            added_news = added_cafe = 0
            for kw in keywords or [cx.name]:
                try:
                    news = [a for a in naver_search.search_news(kw) if _is_relevant(a, kw)]
                    cafe = [a for a in naver_search.search_cafe(kw) if _is_relevant(a, kw)]
                    added_news += ingest.upsert_articles(session, cx.id, news)
                    added_cafe += ingest.upsert_articles(session, cx.id, cafe)
                except naver_search.NaverSearchError as e:
                    all_ok = False
                    lines.append(f"{cx.name}/{kw}: 검색 실패 — {e}")
                    logger.error("기사 수집 실패 (%s/%s): %s", cx.name, kw, e)
            lines.append(f"{cx.name}: 신규 뉴스 {added_news}건, 카페 {added_cafe}건")
        detail = "\n".join(lines) or "등록된 단지 없음"
        _log_run(session, "articles", started, all_ok, detail)
    return detail


JOBS = {
    "listings": run_listings_job,
    "transactions": run_transactions_job,
    "articles": run_articles_job,
}
