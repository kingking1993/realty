"""네이버 검색 API — 뉴스/카페글 키워드 검색 (공식 API).

- 뉴스: pubDate(RFC 822) 제공
- 카페글: 날짜 필드 미제공 → pub_date는 None
title/description의 <b> 태그와 HTML 엔티티는 제거한다.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from app.config import NAVER_CLIENT_ID, NAVER_CLIENT_SECRET

logger = logging.getLogger(__name__)

NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
CAFE_URL = "https://openapi.naver.com/v1/search/cafearticle.json"
DISPLAY = 30  # 키워드당 최신 30건

_TAG_RE = re.compile(r"<[^>]+>")


class NaverSearchError(Exception):
    pass


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text or "")).strip()


def _parse_pub_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _search(url: str, source: str, keyword: str) -> list[dict]:
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        raise NaverSearchError("NAVER_CLIENT_ID/SECRET이 설정되지 않았습니다 (.env 확인)")

    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {"query": keyword, "display": DISPLAY, "sort": "date"}
    try:
        resp = httpx.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except (httpx.HTTPError, ValueError) as e:
        raise NaverSearchError(f"{source} 검색 실패 ({keyword}): {e}") from e

    results = []
    for item in items:
        link = item.get("link", "")
        if not link:
            continue
        results.append(
            {
                "source": source,
                "keyword": keyword,
                "title": _clean(item.get("title", "")),
                "link": link,
                "description": _clean(item.get("description", "")),
                "pub_date": _parse_pub_date(item.get("pubDate", "")),
            }
        )
    return results


def search_news(keyword: str) -> list[dict]:
    return _search(NEWS_URL, "news", keyword)


def search_cafe(keyword: str) -> list[dict]:
    return _search(CAFE_URL, "cafe", keyword)
