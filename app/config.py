"""설정 로드: .env(API 키) + complexes.yaml(단지 목록)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "realty.db"

load_dotenv(BASE_DIR / ".env")

MOLIT_API_KEY = os.getenv("MOLIT_API_KEY", "")
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")


@dataclass
class ComplexConfig:
    name: str
    naver_complex_no: str
    lawd_cd: str
    umd_nm: str = ""
    apt_name_molit: str = ""
    keywords: list[str] = field(default_factory=list)  # 단지 키워드 (topic=complex)
    area_keywords: list[str] = field(default_factory=list)  # 지역 키워드 (topic=area)
    area_label: str = "지역"  # 지역 탭 표시명 (예: 강서구)


def load_complexes(path: Path | None = None) -> list[ComplexConfig]:
    path = path or (BASE_DIR / "complexes.yaml")
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    result = []
    for item in raw.get("complexes", []):
        result.append(
            ComplexConfig(
                name=str(item["name"]),
                naver_complex_no=str(item["naver_complex_no"]),
                lawd_cd=str(item["lawd_cd"]),
                umd_nm=str(item.get("umd_nm") or ""),
                apt_name_molit=str(item.get("apt_name_molit") or ""),
                keywords=[str(k) for k in item.get("keywords") or []],
                area_keywords=[str(k) for k in item.get("area_keywords") or []],
                area_label=str(item.get("area_label") or "지역"),
            )
        )
    return result
