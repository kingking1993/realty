"""단지명으로 네이버 부동산 단지 번호(complexNo) 검색.

사용법:
    python scripts/find_complex.py "등촌 부영"

동작: new.land.naver.com 페이지에서 토큰을 얻어 검색 API를 호출한다.
실패하면 브라우저에서 new.land.naver.com 에 단지를 검색한 뒤 주소창의
/complexes/{번호} 부분을 complexes.yaml에 적으면 된다.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.collectors.naver_land import HEADERS, _JWT_RE, NaverLandError


def _fetch_home_token(client: httpx.Client) -> str:
    resp = client.get("https://new.land.naver.com/complexes")
    resp.raise_for_status()
    m = _JWT_RE.search(resp.text)
    if not m:
        raise NaverLandError("페이지에서 토큰을 찾지 못함 — 사이트 구조 변경 가능성")
    return m.group(0)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    keyword = sys.argv[1]

    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=25) as client:
        token = _fetch_home_token(client)
        time.sleep(1.5)
        resp = client.get(
            "https://new.land.naver.com/api/search",
            params={"keyword": keyword},
            headers={"Accept": "application/json", "Authorization": f"Bearer {token}",
                     "Referer": "https://new.land.naver.com/"},
        )
        resp.raise_for_status()
        data = resp.json()

    complexes = data.get("complexes") or []
    if not complexes:
        print(f"'{keyword}' 검색 결과가 없습니다.")
        print("브라우저에서 new.land.naver.com 에 검색 후 주소창의 /complexes/{번호} 를 확인하세요.")
        return

    print(f"'{keyword}' 검색 결과 {len(complexes)}건:\n")
    for c in complexes:
        ymd = str(c.get("useApproveYmd", ""))
        year = ymd[:4] if len(ymd) >= 4 else "?"
        print(f"  complexNo: {c.get('complexNo'):>8}  {c.get('complexName')}"
              f"  ({c.get('totalHouseholdCount', '?')}세대, {year}년, "
              f"동 {c.get('totalDongCount', '?')}개)")
    print("\ncomplexes.yaml의 naver_complex_no 에 위 번호를 적으세요.")


if __name__ == "__main__":
    main()
