"""수집 잡 수동 즉시 실행.

사용법:
    python scripts/collect_now.py --job listings      # 매물 수집 + diff
    python scripts/collect_now.py --job transactions  # 실거래가 + 매칭
    python scripts/collect_now.py --job articles      # 뉴스/카페
    python scripts/collect_now.py --job all
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db
from app.services.jobs import JOBS


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", choices=[*JOBS, "all"], default="all")
    args = parser.parse_args()

    init_db()
    jobs = list(JOBS) if args.job == "all" else [args.job]
    for name in jobs:
        print(f"\n=== {name} ===")
        print(JOBS[name]())


if __name__ == "__main__":
    main()
