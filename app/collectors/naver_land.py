"""네이버 부동산 매물 스냅샷 수집 (new.land.naver.com).

단지 페이지 HTML에 내장된 JWT 토큰을 추출한 뒤, 같은 세션(쿠키)으로
매물 목록 API를 페이지네이션 호출한다. 개인 이용 목적의 저빈도 수집:
페이지당 1.5~3초 딜레이, 오류 시 지수 백오프.

주의: 같은 집을 여러 중개사가 올리면 매물이 중복 집계된다 (articleNo 기준).
수량 추이를 볼 때는 절대값보다 증감 추세를 보는 것이 정확하다.

API 응답 형식이 바뀔 수 있으므로 파싱은 방어적으로 하고, 실패 시 예외를 올려
호출측(ingest)이 diff를 건너뛰게 한다.
"""
from __future__ import annotations

import logging
import random
import re
import time

import httpx

logger = logging.getLogger(__name__)

COMPLEX_PAGE_URL = "https://new.land.naver.com/complexes/{no}"
ARTICLE_API_URL = "https://new.land.naver.com/api/articles/complex/{no}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")

MAX_PAGES = 100  # 안전 상한 (페이지당 20건 → 최대 2000건)

TRADE_TYPE_NAMES = {"매매", "전세", "월세", "단기임대"}


class NaverLandError(Exception):
    """수집 실패. 호출측은 이 스냅샷으로 diff 하면 안 된다."""


def _parse_price(value) -> int:
    """가격 표기('22억', '22억 5,000', '5,000', 150)를 만원 단위 int로."""
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).replace(",", "").strip()
    if not s:
        return 0
    total = 0
    if "억" in s:
        eok, _, rest = s.partition("억")
        try:
            total += int(float(eok)) * 10000
        except ValueError:
            return 0
        s = rest.strip()
    if s:
        try:
            total += int(float(s))
        except ValueError:
            pass
    return total


def _normalize_article(item: dict) -> dict:
    """API 응답 1건 → listings 테이블에 맞는 dict."""
    return {
        "article_no": str(item.get("articleNo", "")),
        "trade_type": str(item.get("tradeTypeName", "")),  # 매매/전세/월세
        "dong": str(item.get("buildingName", "") or ""),  # 예: "101동"
        "floor_info": str(item.get("floorInfo", "") or ""),  # 예: "12/25", "중/25"
        "area_exclusive": float(item.get("area2") or 0),  # 전용면적 ㎡
        "price": _parse_price(item.get("dealOrWarrantPrc")),  # 매매가/보증금
        "price_monthly": _parse_price(item.get("rentPrc")),  # 월세
        "description": str(item.get("articleFeatureDesc", "") or ""),
    }


def _fetch_token(client: httpx.Client, complex_no: str) -> str:
    """단지 페이지에서 API 호출용 JWT 토큰 추출 (쿠키도 이때 세션에 쌓임)."""
    try:
        resp = client.get(COMPLEX_PAGE_URL.format(no=complex_no))
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise NaverLandError(f"단지 페이지({complex_no}) 접근 실패: {e}") from e
    m = _JWT_RE.search(resp.text)
    if not m:
        raise NaverLandError(f"단지 페이지({complex_no})에서 토큰을 찾지 못함 — 사이트 구조 변경 가능성")
    return m.group(0)


def _fetch_page(client: httpx.Client, token: str, complex_no: str, page: int) -> dict:
    params = {
        "realEstateType": "APT",
        "tradeType": "",
        "page": page,
        "complexNo": complex_no,
        "type": "list",
        "order": "rank",
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Referer": COMPLEX_PAGE_URL.format(no=complex_no),
    }
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.get(ARTICLE_API_URL.format(no=complex_no), params=params,
                              headers=headers, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "articleList" in data:
                    return data
                raise NaverLandError(f"예상 밖 응답 형식: {str(data)[:200]}")
            last_err = NaverLandError(f"HTTP {resp.status_code}")
        except (httpx.HTTPError, ValueError) as e:
            last_err = e
        # 지수 백오프
        time.sleep(5 * (2**attempt) + random.uniform(0, 2))
    raise NaverLandError(f"페이지 {page} 수집 실패: {last_err}")


def fetch_listings(complex_no: str) -> list[dict]:
    """단지의 전체 매물 스냅샷을 수집해 정규화된 dict 목록으로 반환.

    실패 시 NaverLandError — 부분 수집본을 반환하지 않는다 (diff 오판 방지).
    """
    articles: list[dict] = []
    seen: set[str] = set()
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        token = _fetch_token(client, complex_no)
        time.sleep(random.uniform(1.0, 2.0))
        for page in range(1, MAX_PAGES + 1):
            data = _fetch_page(client, token, complex_no, page)
            for item in data.get("articleList") or []:
                norm = _normalize_article(item)
                if norm["article_no"] and norm["article_no"] not in seen:
                    seen.add(norm["article_no"])
                    articles.append(norm)
            if not data.get("isMoreData"):
                break
            time.sleep(random.uniform(1.5, 3.0))
    logger.info("complex %s: 매물 %d건 수집", complex_no, len(articles))
    return articles


def fetch_complex_name(complex_no: str) -> str:
    """단지 페이지 <title>에서 단지명 추출 (등록 확인용)."""
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        resp = client.get(COMPLEX_PAGE_URL.format(no=complex_no))
        m = re.search(r"<title>([^<]*)</title>", resp.text)
        return m.group(1).strip() if m else ""
