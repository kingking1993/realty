"""Blind(teamblind.com) 검색 결과 수집.

검색 페이지의 서버렌더링 HTML에서 게시글 링크·제목을 추출한다.
본문과 작성일은 로그인이 필요해 제목+링크만 수집한다 (pub_date=None).
비공식 수집이므로 저빈도로만 호출하고, 실패해도 다른 수집에 영향 주지 않는다.
"""
from __future__ import annotations

import html as html_mod
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import httpx

KST = timezone(timedelta(hours=9))

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.teamblind.com/kr/search/{query}"
BASE = "https://www.teamblind.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_POST_RE = re.compile(r'<a[^>]+href="(/kr/post/[^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_DATE_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')


class BlindError(Exception):
    pass


def parse_posts(page_html: str) -> list[dict]:
    """검색 결과 HTML → 게시글 dict 목록 (링크 기준 중복 제거)."""
    results: list[dict] = []
    seen: set[str] = set()
    for m in _POST_RE.finditer(page_html):
        path, inner = m.group(1), m.group(2)
        link = BASE + path.split("?")[0]
        title = html_mod.unescape(_TAG_RE.sub("", inner)).strip()
        if not title or link in seen:
            continue
        seen.add(link)
        results.append({
            "source": "blind",
            "title": title,
            "link": link,
            "description": "",
            "pub_date": None,
        })
    return results


def fetch_post_date(link: str) -> datetime | None:
    """글 페이지의 JSON-LD datePublished → KST naive datetime. 실패 시 None."""
    try:
        resp = httpx.get(link, headers=HEADERS, timeout=20, follow_redirects=True)
        resp.raise_for_status()
        m = _DATE_RE.search(resp.text)
        if not m:
            return None
        raw = m.group(1).replace("Z", "+00:00")
        return datetime.fromisoformat(raw).astimezone(KST).replace(tzinfo=None)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Blind 작성일 조회 실패 (%s): %s", link, e)
        return None


def search_blind(keyword: str) -> list[dict]:
    try:
        resp = httpx.get(SEARCH_URL.format(query=quote(keyword)), headers=HEADERS,
                         timeout=20, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise BlindError(f"Blind 검색 실패 ({keyword}): {e}") from e
    posts = parse_posts(resp.text)
    for p in posts:
        p["keyword"] = keyword
    return posts
