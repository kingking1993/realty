"""FastAPI 앱: 웹 화면 + APScheduler 수집 스케줄."""
from __future__ import annotations

import base64
import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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
from app.services.jobs import JOBS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE / "templates")

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
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

APP_PASSWORD = os.getenv("APP_PASSWORD", "")


@app.middleware("http")
async def basic_auth(request: Request, call_next):
    """APP_PASSWORD 가 설정된 경우에만 전체 접근을 비밀번호로 보호.

    /collect/* 는 외부 크론(cron-job.org)이 호출할 수 있도록
    ?key=<APP_PASSWORD> 쿼리 파라미터도 허용한다.
    """
    if APP_PASSWORD:
        authorized = False
        auth = request.headers.get("authorization", "")
        if auth.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth[6:]).decode("utf-8")
                _, _, password = decoded.partition(":")
                authorized = secrets.compare_digest(password, APP_PASSWORD)
            except Exception:
                authorized = False
        if not authorized and request.url.path.startswith("/collect/"):
            key = request.query_params.get("key", "")
            authorized = secrets.compare_digest(key, APP_PASSWORD)
        if not authorized:
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="realty"'},
            )
    return await call_next(request)


def _fmt_price(price: int, monthly: int = 0) -> str:
    """만원 → '12.5억' 표기 (한 줄 고정용 축약형)."""
    if price <= 0:
        return "-"
    s = f"{price / 10000:g}억" if price >= 10000 else f"{price:,}"
    if monthly:
        s += f"/{monthly:,}"
    return s


def _fmt_date_short(value) -> str:
    """date/datetime → '7/13' 표기."""
    return f"{value.month}/{value.day}" if value else "-"


templates.env.filters["price"] = _fmt_price
templates.env.filters["d"] = _fmt_date_short


def _topic_labels() -> dict[str, str]:
    cfgs = load_complexes()
    return {
        "complex": cfgs[0].name if cfgs else "단지",
        "area": cfgs[0].area_label if cfgs else "지역",
    }


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, src: str = "", topic: str = ""):
    with session_scope() as s:
        complexes = list(s.scalars(select(Complex).order_by(Complex.name)))
        cards = []
        for cx in complexes:
            dates = list(s.scalars(
                select(DailyCount.date).where(DailyCount.complex_id == cx.id)
                .distinct().order_by(desc(DailyCount.date)).limit(2)
            ))
            counts: dict[str, tuple[int, int | None]] = {}
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
                counts[tt] = (today_n or 0, prev_n)
            cards.append({"cx": cx, "counts": counts,
                          "as_of": dates[0] if dates else None})

        events = s.execute(
            select(ListingEvent, Listing, Complex)
            .join(Listing, ListingEvent.listing_id == Listing.id)
            .join(Complex, Listing.complex_id == Complex.id)
            .order_by(desc(ListingEvent.occurred_at)).limit(15)
        ).all()

        aq = select(Article).order_by(
            desc(Article.pub_date).nulls_last(), desc(Article.fetched_at)
        ).limit(10)
        if src in ("news", "cafe", "blind"):
            aq = aq.where(Article.source == src)
        if topic in ("complex", "area"):
            aq = aq.where(Article.topic == topic)
        articles = list(s.scalars(aq))

        logs = {}
        for job in JOBS:
            logs[job] = s.scalar(
                select(CollectionLog).where(CollectionLog.job == job)
                .order_by(desc(CollectionLog.started_at)).limit(1)
            )

        return templates.TemplateResponse(request, "dashboard.html", {
            "cards": cards, "events": events, "articles": articles, "logs": logs,
            "src": src, "topic": topic, "topic_labels": _topic_labels(),
        })


@app.get("/complex/{complex_id}", response_class=HTMLResponse)
def complex_detail(request: Request, complex_id: int, trade_type: str = "매매"):
    with session_scope() as s:
        cx = s.get(Complex, complex_id)
        if cx is None:
            return RedirectResponse("/")

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

        listings = list(s.scalars(
            select(Listing).where(
                Listing.complex_id == complex_id, Listing.status == "active",
                Listing.trade_type == trade_type,
            ).order_by(Listing.dong, Listing.area_exclusive, Listing.price)
        ))

        events = s.execute(
            select(ListingEvent, Listing)
            .join(Listing, ListingEvent.listing_id == Listing.id)
            .where(Listing.complex_id == complex_id)
            .order_by(desc(ListingEvent.occurred_at)).limit(100)
        ).all()

        matches = {
            m.listing_id: m for m in s.scalars(
                select(Match).join(Listing, Match.listing_id == Listing.id)
                .where(Listing.complex_id == complex_id)
            )
        }
        txns_by_id = {t.id: t for t in s.scalars(
            select(Transaction).where(Transaction.complex_id == complex_id))}

        transactions = list(s.scalars(
            select(Transaction).where(Transaction.complex_id == complex_id)
            .order_by(desc(Transaction.deal_date)).limit(100)
        ))
        matched_txn_listing = {m.transaction_id: m.listing_id for m in matches.values()}

        return templates.TemplateResponse(request, "complex_detail.html", {
            "cx": cx, "chart": chart, "listings": listings, "events": events,
            "matches": matches, "txns_by_id": txns_by_id,
            "transactions": transactions, "matched_txn_listing": matched_txn_listing,
            "trade_type": trade_type,
        })


@app.get("/feed", response_class=HTMLResponse)
def feed(request: Request, source: str = "", topic: str = "", complex_id: int = 0):
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
        articles = list(s.scalars(q))
        complexes = list(s.scalars(select(Complex).order_by(Complex.name)))
        return templates.TemplateResponse(request, "feed.html", {
            "articles": articles, "complexes": complexes,
            "source": source, "topic": topic, "complex_id": complex_id,
            "topic_labels": _topic_labels(),
        })


@app.api_route("/collect/{job}", methods=["GET", "POST"])
def collect_now(job: str):
    """수집 트리거 — 화면 버튼(POST)과 외부 크론(GET) 공용. 백그라운드 스레드로 실행."""
    if job not in JOBS:
        return {"ok": False, "error": "unknown job"}
    threading.Thread(target=JOBS[job], name=f"collect-{job}", daemon=True).start()
    return {"ok": True, "job": job}
