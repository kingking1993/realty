"""수집 잡 오케스트레이션. 스케줄러(main.py)와 수동 실행(scripts/collect_now.py)이 공용."""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime

from app.collectors import blind, molit, naver_land, naver_search
from app.config import load_complexes
from app.db import session_scope
from app.models import CollectionLog
from app.services import ingest, matcher

logger = logging.getLogger(__name__)


def _is_relevant(item: dict, keyword: str, mode: str = "strict") -> bool:
    """검색 결과가 키워드와 실제로 관련 있는지 필터.

    - strict: 키워드가 (공백 무시하고) 통째로 등장해야 함 — 단지 키워드용.
      '등촌부영' 검색에 '등촌'과 '부영그룹'이 따로 나오는 기사를 거른다.
    - tokens: 키워드의 각 단어가 모두 등장하면 통과 — 지역 키워드용.
      '강서구 부동산'이 "강서구 아파트값·부동산 시장…"처럼 떨어져 나와도 잡는다.
    """
    text = (item.get("title", "") + " " + item.get("description", "")).replace(" ", "")
    if mode == "tokens":
        return all(tok in text for tok in keyword.split())
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
                snapshot, counts = naver_land.fetch_listings(cx.naver_complex_no)
            except naver_land.NaverLandError as e:
                all_ok = False
                lines.append(f"{cx.name}: 수집 실패 — {e} (diff 건너뜀)")
                logger.error("%s 매물 수집 실패: %s", cx.name, e)
                continue
            stats = ingest.ingest_listing_snapshot(session, cx.id, snapshot)
            ingest.record_daily_counts(session, cx.id, counts=counts or None)
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
    """단지별 키워드로 뉴스/카페/블라인드 글 수집.

    키워드 그룹: keywords → topic=complex(단지, strict 필터),
    area_keywords → topic=area(지역, tokens 필터).
    """
    started = datetime.now()
    lines: list[str] = []
    all_ok = True
    with session_scope() as session:
        complexes = ingest.sync_complexes(session)
        cfg_by_no = {c.naver_complex_no: c for c in load_complexes()}
        for cx in complexes:
            cfg = cfg_by_no.get(cx.naver_complex_no)
            groups = [
                ("complex", "strict", (cfg.keywords if cfg else None) or [cx.name]),
                ("area", "tokens", cfg.area_keywords if cfg else []),
            ]
            added = {"news": 0, "cafe": 0, "blind": 0}
            for topic, mode, keywords in groups:
                for kw in keywords:
                    try:
                        news = [a for a in naver_search.search_news(kw) if _is_relevant(a, kw, mode)]
                        cafe = [a for a in naver_search.search_cafe(kw) if _is_relevant(a, kw, mode)]
                        added["news"] += ingest.upsert_articles(session, cx.id, news, topic=topic)
                        added["cafe"] += ingest.upsert_articles(session, cx.id, cafe, topic=topic)
                    except naver_search.NaverSearchError as e:
                        all_ok = False
                        lines.append(f"{cx.name}/{kw}: 검색 실패 — {e}")
                        logger.error("기사 수집 실패 (%s/%s): %s", cx.name, kw, e)
                    try:
                        posts = [p for p in blind.search_blind(kw) if _is_relevant(p, kw, mode)]
                        # 새 글만 글 페이지를 열어 작성일 확보 (저빈도 유지용 딜레이)
                        new_posts = ingest.filter_new_articles(session, posts)
                        for p in new_posts:
                            p["pub_date"] = blind.fetch_post_date(p["link"])
                            time.sleep(random.uniform(0.5, 1.2))
                        added["blind"] += ingest.upsert_articles(session, cx.id, new_posts, topic=topic)
                    except blind.BlindError as e:
                        # Blind는 부가 소스 — 실패해도 잡 전체를 실패로 치지 않음
                        lines.append(f"{cx.name}/{kw}: Blind 실패 — {e}")
                        logger.warning("Blind 수집 실패 (%s/%s): %s", cx.name, kw, e)
            lines.append(
                f"{cx.name}: 신규 뉴스 {added['news']}건, 카페 {added['cafe']}건, "
                f"블라인드 {added['blind']}건"
            )
        detail = "\n".join(lines) or "등록된 단지 없음"
        _log_run(session, "articles", started, all_ok, detail)
    return detail


JOBS = {
    "listings": run_listings_job,
    "transactions": run_transactions_job,
    "articles": run_articles_job,
}
