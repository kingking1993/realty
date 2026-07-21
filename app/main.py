"""FastAPI 앱: JSON API + React SPA 서빙 + APScheduler 수집 스케줄."""
from __future__ import annotations

import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import desc, select

from app.config import load_complexes
from app.db import init_db, session_scope
from app.models import (
    Article,
    CollectionLog,
    Complex,
    DailyCount,
    Listing,
    ListingEvent,
    Match,
    Transaction,
)
from app.services import ingest, matcher
from app.services.jobs import JOBS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
FRONTEND_DIST = BASE.parent / "frontend" / "dist"

scheduler = BackgroundScheduler()


def _setup_schedule() -> None:
    # 매물: 10:00, 18:00 / 실거래+매칭: 11:00 / 뉴스·카페: 08,12,17,21시
    scheduler.add_job(JOBS["listings"], "cron", hour="10,18", minute=0, id="listings",
                      misfire_grace_time=3600, coalesce=True)
    scheduler.add_job(JOBS["transactions"], "cron", hour=11, minute=0, id="transactions",
                      misfire_grace_time=3600, coalesce=True)
    scheduler.add_job(JOBS["articles"], "cron", hour="8,12,17,21", minute=0, id="articles",
                      misfire_grace_time=3600, coalesce=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 클라우드(잠드는 무료 티어)에서는 외부 크론이 /collect 를 호출하므로
    # 내부 스케줄러를 끈다 (DISABLE_SCHEDULER=1)
    if os.getenv("DISABLE_SCHEDULER") != "1":
        _setup_schedule()
        scheduler.start()
        logger.info("스케줄러 시작")
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Realty", lifespan=lifespan)

APP_PASSWORD = os.getenv("APP_PASSWORD", "")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """/collect/* 만 APP_PASSWORD(?key=)로 보호. 화면·API는 공개.

    /collect/* 는 외부 크론(cron-job.org)이 호출할 수 있도록
    ?key=<APP_PASSWORD> 쿼리 파라미터로 인증한다.
    """
    if APP_PASSWORD and request.url.path.startswith("/collect/"):
        key = request.query_params.get("key", "")
        if not secrets.compare_digest(key, APP_PASSWORD):
            return Response(status_code=401)
    return await call_next(request)


def _topic_labels() -> dict[str, str]:
    cfgs = load_complexes()
    return {
        "complex": cfgs[0].name if cfgs else "단지",
        "area": cfgs[0].area_label if cfgs else "지역",
    }


def _article_json(a: Article) -> dict:
    return {
        "id": a.id,
        "source": a.source,
        "keyword": a.keyword,
        "topic": a.topic,
        "title": a.title,
        "link": a.link,
        "description": a.description,
        "pub_date": a.pub_date.isoformat() if a.pub_date else None,
        "fetched_at": a.fetched_at.isoformat() if a.fetched_at else None,
    }


def _fmt_confirm(ymd: str) -> str | None:
    """네이버 등록일 'YYYYMMDD' → 'YYYY-MM-DD' (표시·정렬용)."""
    if ymd and len(ymd) == 8 and ymd.isdigit():
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
    return None


def _event_json(ev: ListingEvent, l: Listing) -> dict:
    return {
        "id": ev.id,
        "event": ev.event,
        "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
        "old_price": ev.old_price,
        "new_price": ev.new_price,
        "trade_type": l.trade_type,
        "dong": l.dong,
        "floor_info": l.floor_info,
        "price": l.price,
        "price_monthly": l.price_monthly,
        "listing_id": l.id,
        "confirm_date": _fmt_confirm(l.confirm_date),
    }


def _dedup_events(rows: list[dict], extra_key=lambda r: ()) -> list[dict]:
    """같은 세대를 여러 중개사가 중복 게재한 이벤트를 병합하고 dup_count 부여.

    rows는 최신순 정렬 상태를 가정하며, 병합 시 첫 행(최신)을 대표로 남긴다.
    """
    seen: dict[tuple, dict] = {}
    result: list[dict] = []
    for row in rows:
        key = (
            row["trade_type"], row["dong"], row["floor_info"],
            row["event"], row["old_price"], row["new_price"],
            row["price_monthly"], *extra_key(row),
        )
        if key in seen:
            seen[key]["dup_count"] += 1
        else:
            row["dup_count"] = 1
            seen[key] = row
            result.append(row)
    return result


# ============================================================
# 현재 매물 · 변동 상태 계산 헬퍼
# ============================================================

def _price_change_dir(session, complex_id: int) -> dict[int, str]:
    """listing_id → '인하'/'인상' (가장 최근 PRICE_CHANGED 기준)."""
    out: dict[int, str] = {}
    for ev in session.execute(
        select(ListingEvent).join(Listing, ListingEvent.listing_id == Listing.id)
        .where(Listing.complex_id == complex_id, ListingEvent.event == "PRICE_CHANGED")
        .order_by(ListingEvent.occurred_at)
    ).scalars():
        if ev.old_price and ev.new_price and ev.new_price != ev.old_price:
            out[ev.listing_id] = "인하" if ev.new_price < ev.old_price else "인상"
    return out


def _active_listings(session, complex_id: int, trade_type: str,
                     change_dir: dict[int, str], today: str) -> list[dict]:
    """현재 active 매물을 개별(중복 묶지 않음)로 반환. change: 신규(당일)/인하/인상/None."""
    rows = []
    for l in session.scalars(
        select(Listing).where(
            Listing.complex_id == complex_id, Listing.status == "active",
            Listing.trade_type == trade_type,
        ).order_by(Listing.dong, Listing.floor_info, Listing.price)
    ):
        is_new = _fmt_confirm(l.confirm_date) == today
        rows.append({
            "id": l.id, "dong": l.dong, "floor_info": l.floor_info,
            "price": l.price, "price_monthly": l.price_monthly,
            "confirm_date": _fmt_confirm(l.confirm_date),
            "change": "신규" if is_new else change_dir.get(l.id),
        })
    return rows


# ============================================================
# JSON API
# ============================================================

@app.get("/api/dashboard")
def api_dashboard(src: str = "", topic: str = ""):
    with session_scope() as s:
        today = date.today().isoformat()
        complexes = list(s.scalars(select(Complex).order_by(Complex.name)))
        cards = []
        for cx in complexes:
            dates = list(s.scalars(
                select(DailyCount.date).where(DailyCount.complex_id == cx.id)
                .distinct().order_by(desc(DailyCount.date)).limit(2)
            ))
            counts: dict[str, list[int | None]] = {}
            for tt in ("매매", "전세", "월세"):
                today_n = prev_n = None
                if dates:
                    today_n = s.scalar(select(DailyCount.count).where(
                        DailyCount.complex_id == cx.id, DailyCount.date == dates[0],
                        DailyCount.trade_type == tt))
                if len(dates) > 1:
                    prev_n = s.scalar(select(DailyCount.count).where(
                        DailyCount.complex_id == cx.id, DailyCount.date == dates[1],
                        DailyCount.trade_type == tt))
                counts[tt] = [today_n or 0, prev_n]
            change_dir = _price_change_dir(s, cx.id)
            listings = {
                tt: _active_listings(s, cx.id, tt, change_dir, today)
                for tt in ("매매", "전세", "월세")
            }
            cards.append({
                "id": cx.id, "name": cx.name, "counts": counts,
                "as_of": dates[0].isoformat() if dates else None,
                "listings": listings,
            })

        aq = select(Article).order_by(
            desc(Article.pub_date).nulls_last(), desc(Article.fetched_at)
        ).limit(10)
        if src in ("news", "cafe", "blind"):
            aq = aq.where(Article.source == src)
        if topic in ("complex", "area"):
            aq = aq.where(Article.topic == topic)
        articles = [_article_json(a) for a in s.scalars(aq)]

        logs = {}
        for job in JOBS:
            log = s.scalar(
                select(CollectionLog).where(CollectionLog.job == job)
                .order_by(desc(CollectionLog.started_at)).limit(1)
            )
            logs[job] = {
                "started_at": log.started_at.isoformat(), "ok": log.ok,
            } if log else None

        return {
            "cards": cards, "articles": articles,
            "logs": logs, "topic_labels": _topic_labels(),
        }


@app.get("/api/complex/{complex_id}")
def api_complex_detail(complex_id: int, trade_type: str = "매매"):
    with session_scope() as s:
        cx = s.get(Complex, complex_id)
        if cx is None:
            return Response(status_code=404)

        since = date.today() - timedelta(days=90)
        chart_rows = s.execute(
            select(DailyCount).where(
                DailyCount.complex_id == complex_id, DailyCount.date >= since
            ).order_by(DailyCount.date)
        ).scalars().all()
        chart_dates = sorted({r.date.isoformat() for r in chart_rows})
        chart_series = {tt: {r.date.isoformat(): r.count for r in chart_rows if r.trade_type == tt}
                        for tt in ("매매", "전세", "월세")}
        chart = {
            "labels": chart_dates,
            "series": [
                {"label": tt, "data": [chart_series[tt].get(d) for d in chart_dates]}
                for tt in ("매매", "전세", "월세")
            ],
        }

        # 같은 세대(동·층·면적·가격)를 여러 중개사가 올린 중복 매물 병합
        listing_groups: dict[tuple, dict] = {}
        for l in s.scalars(
            select(Listing).where(
                Listing.complex_id == complex_id, Listing.status == "active",
                Listing.trade_type == trade_type,
            ).order_by(Listing.dong, Listing.area_exclusive, Listing.price)
        ):
            key = ingest.listing_unit_key(l)
            g = listing_groups.get(key)
            if g is None:
                listing_groups[key] = {
                    "id": l.id, "dong": l.dong, "floor_info": l.floor_info,
                    "price": l.price, "price_monthly": l.price_monthly,
                    "description": l.description,
                    "first_seen": l.first_seen.isoformat() if l.first_seen else None,
                    "dup_count": 1,
                }
            else:
                g["dup_count"] += 1
                # 가장 먼저 등록된 시점을 대표로
                fs = l.first_seen.isoformat() if l.first_seen else None
                if fs and (g["first_seen"] is None or fs < g["first_seen"]):
                    g["first_seen"] = fs
        listings = list(listing_groups.values())

        matches = {
            m.listing_id: m for m in s.scalars(
                select(Match).join(Listing, Match.listing_id == Listing.id)
                .where(Listing.complex_id == complex_id)
            )
        }
        txns_by_id = {t.id: t for t in s.scalars(
            select(Transaction).where(Transaction.complex_id == complex_id))}

        events = []
        for ev, l in s.execute(
            select(ListingEvent, Listing)
            .join(Listing, ListingEvent.listing_id == Listing.id)
            .where(Listing.complex_id == complex_id)
            .order_by(desc(ListingEvent.occurred_at)).limit(300)
        ).all():
            e = _event_json(ev, l)
            m = matches.get(l.id)
            if ev.event == "REMOVED" and m and m.transaction_id in txns_by_id:
                t = txns_by_id[m.transaction_id]
                e["match"] = {
                    "confidence": m.confidence,
                    "deal_date": t.deal_date.isoformat(),
                    "price": t.price, "floor": t.floor, "apt_dong": t.apt_dong,
                }
            events.append(e)
        events = _dedup_events(events)[:100]

        matched_txn_ids = {m.transaction_id for m in matches.values()}
        transactions = [
            {
                "id": t.id, "deal_date": t.deal_date.isoformat(),
                "apt_dong": t.apt_dong, "floor": t.floor, "price": t.price,
                "is_canceled": t.is_canceled,
                "matched": t.id in matched_txn_ids,
            }
            for t in s.scalars(
                select(Transaction).where(Transaction.complex_id == complex_id)
                .order_by(desc(Transaction.deal_date)).limit(100)
            )
        ]

        return {
            "complex": {"id": cx.id, "name": cx.name},
            "chart": chart, "listings": listings, "events": events,
            "transactions": transactions, "trade_type": trade_type,
        }


@app.get("/api/changes")
def api_changes():
    """매물 변동 — 전체 매물을 한 목록으로(중복 안 묶음), 각 행에 변동(신규/유지/재등록/
    인상/인하/소멸) 표시. 카테고리별 개수와 함께 반환하며 기간 제한은 없다(전체 로그).

    신규/유지/재등록/인상/인하는 현재 active 매물의 상태, 소멸은 사라진 매물이다.
    """
    today = date.today().isoformat()
    with session_scope() as s:
        # 재등록 추정: {새_매물_id: 이전_소멸_매물_id}
        relistings = matcher.find_relistings(s)
        relisted_new_ids = set(relistings)
        prev_by_id = {rid: s.get(Listing, rid) for rid in set(relistings.values())}
        removed_to_new = {old_id: new_id for new_id, old_id in relistings.items()}

        # 가장 최근 PRICE_CHANGED 방향 (listing_id → 인하/인상)
        change_dir: dict[int, str] = {}
        for ev in s.execute(
            select(ListingEvent).order_by(ListingEvent.occurred_at)
        ).scalars():
            if ev.event == "PRICE_CHANGED" and ev.old_price and ev.new_price \
                    and ev.new_price != ev.old_price:
                change_dir[ev.listing_id] = "인하" if ev.new_price < ev.old_price else "인상"

        rows: list[dict] = []
        stats = {k: 0 for k in ("신규", "유지", "재등록", "인상", "인하", "소멸")}

        # ---- 현재 active 매물 (개별, 중복 안 묶음) ----
        for l, cx in s.execute(
            select(Listing, Complex).join(Complex, Listing.complex_id == Complex.id)
            .where(Listing.status == "active")
            .order_by(Listing.dong, Listing.floor_info, Listing.price)
        ).all():
            if l.id in relisted_new_ids:
                change = "재등록"
            elif _fmt_confirm(l.confirm_date) == today:
                change = "신규"
            elif l.id in change_dir:
                change = change_dir[l.id]  # 인하/인상
            else:
                change = "유지"
            stats[change] += 1
            prev = prev_by_id.get(relistings.get(l.id))
            rows.append({
                "id": l.id, "complex": {"id": cx.id, "name": cx.name},
                "trade_type": l.trade_type, "dong": l.dong, "floor_info": l.floor_info,
                "price": l.price, "price_monthly": l.price_monthly,
                "confirm_date": _fmt_confirm(l.confirm_date), "occurred_at": None,
                "change": change,
                "relisted_from": {
                    "removed_at": prev.removed_at.isoformat() if prev and prev.removed_at else None,
                } if prev else None,
            })

        # ---- 소멸 매물 (전체 로그) + 실거래/재등록 표시 ----
        removed_raw = s.execute(
            select(ListingEvent, Listing, Complex)
            .join(Listing, ListingEvent.listing_id == Listing.id)
            .join(Complex, Listing.complex_id == Complex.id)
            .where(ListingEvent.event == "REMOVED")
            .order_by(desc(ListingEvent.occurred_at))
        ).all()
        matches = {
            m.listing_id: m for m in s.scalars(
                select(Match).where(Match.listing_id.in_([l.id for _, l, _ in removed_raw]))
            )
        } if removed_raw else {}
        txns = {
            t.id: t for t in s.scalars(select(Transaction).where(
                Transaction.id.in_([m.transaction_id for m in matches.values()])
            ))
        } if matches else {}
        new_by_id = {nid: s.get(Listing, nid) for nid in removed_to_new.values()}

        for ev, l, cx in removed_raw:
            stats["소멸"] += 1
            row = {
                "id": f"r{ev.id}", "complex": {"id": cx.id, "name": cx.name},
                "trade_type": l.trade_type, "dong": l.dong, "floor_info": l.floor_info,
                "price": l.price, "price_monthly": l.price_monthly,
                "confirm_date": _fmt_confirm(l.confirm_date),
                "occurred_at": ev.occurred_at.isoformat() if ev.occurred_at else None,
                "change": "소멸",
            }
            m = matches.get(l.id)
            if m and m.transaction_id in txns:
                t = txns[m.transaction_id]
                row["match"] = {
                    "confidence": m.confidence, "deal_date": t.deal_date.isoformat(),
                    "price": t.price, "floor": t.floor, "apt_dong": t.apt_dong,
                }
            else:
                nl = new_by_id.get(removed_to_new.get(l.id))
                if nl is not None:
                    row["relisted_as"] = {
                        "confirm_date": _fmt_confirm(nl.confirm_date),
                        "first_seen": nl.first_seen.isoformat() if nl.first_seen else None,
                    }
            rows.append(row)

        return {"stats": stats, "rows": rows}


@app.get("/api/feed")
def api_feed(source: str = "", topic: str = "", complex_id: int = 0):
    with session_scope() as s:
        q = select(Article).order_by(
            desc(Article.pub_date).nulls_last(), desc(Article.fetched_at)
        ).limit(200)
        if source in ("news", "cafe", "blind"):
            q = q.where(Article.source == source)
        if topic in ("complex", "area"):
            q = q.where(Article.topic == topic)
        if complex_id:
            q = q.where(Article.complex_id == complex_id)
        articles = [_article_json(a) for a in s.scalars(q)]
        complexes = [
            {"id": cx.id, "name": cx.name}
            for cx in s.scalars(select(Complex).order_by(Complex.name))
        ]
        return {
            "articles": articles, "complexes": complexes,
            "topic_labels": _topic_labels(),
        }


@app.api_route("/collect/{job}", methods=["GET", "POST"])
def collect_now(job: str):
    """수집 트리거 — 화면 버튼(POST)과 외부 크론(GET) 공용. 백그라운드 스레드로 실행."""
    if job not in JOBS:
        return {"ok": False, "error": "unknown job"}
    threading.Thread(target=JOBS[job], name=f"collect-{job}", daemon=True).start()
    return {"ok": True, "job": job}


# ============================================================
# React SPA 서빙 (frontend/dist) — API 라우트 뒤에 등록해야 함
# ============================================================

if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", response_class=HTMLResponse)
def spa(full_path: str):
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(
        "<h1>Realty</h1><p>프론트엔드 빌드가 없습니다. "
        "<code>cd frontend && npm install && npm run build</code> 를 실행하세요.</p>"
    )
