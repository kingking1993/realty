"""국토교통부 아파트 매매 실거래가 수집 (공공데이터포털 API, XML 응답).

법정동코드 5자리 + 계약년월(YYYYMM)로 조회한다. 신고 지연(계약 후 30일)과
계약 해제를 반영하기 위해 매일 최근 3개월치를 재조회해 upsert 한다.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date

import httpx

from app.config import MOLIT_API_KEY

logger = logging.getLogger(__name__)

API_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade"
NUM_OF_ROWS = 1000


class MolitError(Exception):
    pass


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def _parse_item(item: ET.Element) -> dict | None:
    """XML item → transactions 테이블에 맞는 dict."""
    try:
        deal_amount = int(_text(item, "dealAmount").replace(",", ""))  # 만원
        deal_date = date(
            int(_text(item, "dealYear")),
            int(_text(item, "dealMonth")),
            int(_text(item, "dealDay")),
        )
        floor_s = _text(item, "floor")
        return {
            "apt_name": _text(item, "aptNm"),
            "deal_date": deal_date,
            "price": deal_amount,
            "area_exclusive": float(_text(item, "excluUseAr") or 0),
            "floor": int(floor_s) if floor_s else 0,
            "apt_dong": _text(item, "aptDong"),  # 등기 완료 건만 채워짐
            "is_canceled": _text(item, "cdealType").upper() == "O",  # 계약 해제 여부
            "umd_nm": _text(item, "umdNm"),  # 법정동 (참고용)
        }
    except (ValueError, TypeError) as e:
        logger.warning("실거래 항목 파싱 실패: %s", e)
        return None


def fetch_trades(lawd_cd: str, deal_ymd: str) -> list[dict]:
    """시군구(lawd_cd) + 계약년월(deal_ymd, YYYYMM)의 전체 매매 실거래 반환."""
    if not MOLIT_API_KEY:
        raise MolitError("MOLIT_API_KEY가 설정되지 않았습니다 (.env 확인)")

    trades: list[dict] = []
    page = 1
    with httpx.Client() as client:
        while True:
            params = {
                "serviceKey": MOLIT_API_KEY,
                "LAWD_CD": lawd_cd,
                "DEAL_YMD": deal_ymd,
                "pageNo": page,
                "numOfRows": NUM_OF_ROWS,
            }
            try:
                resp = client.get(API_URL, params=params, timeout=30)
                resp.raise_for_status()
                root = ET.fromstring(resp.text)
            except (httpx.HTTPError, ET.ParseError) as e:
                raise MolitError(f"실거래가 API 호출 실패 ({lawd_cd}/{deal_ymd}): {e}") from e

            result_code = (root.findtext(".//resultCode") or "").strip()
            if result_code not in ("00", "000"):
                msg = (root.findtext(".//resultMsg") or "").strip()
                raise MolitError(f"실거래가 API 오류 응답: {result_code} {msg}")

            items = root.findall(".//item")
            for item in items:
                parsed = _parse_item(item)
                if parsed:
                    trades.append(parsed)

            total = int((root.findtext(".//totalCount") or "0").strip() or 0)
            if page * NUM_OF_ROWS >= total or not items:
                break
            page += 1

    logger.info("%s/%s: 실거래 %d건 수집", lawd_cd, deal_ymd, len(trades))
    return trades


def recent_deal_ymds(today: date | None = None, months: int = 3) -> list[str]:
    """당월 포함 최근 N개월의 YYYYMM 목록."""
    today = today or date.today()
    result = []
    y, m = today.year, today.month
    for _ in range(months):
        result.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return result
