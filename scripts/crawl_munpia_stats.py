"""문피아 목록 API 전용 통계(좋아요/선호작/댓글 등) 백필 크롤러.

작품 상세·회차 호출 없이 목록 페이지만 순회하므로 본 크롤(scripts/crawl_munpia.py)보다
훨씬 저비용이다. 출력 디렉토리를 본 크롤과 분리해(기본 data/raw/stats) 체크포인트 충돌을
피한다.

    uv run python scripts/crawl_munpia_stats.py --max-pages 1   # 소규모 테스트
    uv run python scripts/crawl_munpia_stats.py --max-pages 0 --delay 0.8   # 전체 실행

⚠️ --max-pages 기본값은 1이다. 전체를 돌리려면 반드시 --max-pages 0을 붙일 것
(빠뜨리면 조용히 1페이지=20건만 수집하고 정상 종료한다).
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawler.config import CrawlConfig  # noqa: E402
from clawler.stats_runner import run_stats_crawl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="문피아 목록 통계(좋아요/선호작 등) 백필 크롤러")
    parser.add_argument(
        "--section",
        default="nv.free",
        help="목록 섹션 (nv.free/pl.serial/pl.serial_end 등, 기본 nv.free)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="목록 페이지 최대 크롤링 수 (기본 1, 안전을 위한 기본값). 0이면 전체 페이지",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw/stats"),
        help="CSV 출력 디렉토리 (기본 data/raw/stats — 본 크롤과 분리)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="요청 간 지연 시간(초). 미지정 시 CrawlConfig 기본값 사용",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="output-dir에서 가장 최근 체크포인트를 찾아 이어서 크롤링",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="목록 시작 페이지 (기본 1). --resume 시 앞 페이지 재스캔을 건너뛰려면 지정",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = CrawlConfig.from_env()
    overrides = {"section": args.section}
    if args.delay is not None:
        overrides["request_delay_seconds"] = args.delay
    config = dataclasses.replace(config, **overrides)

    summary = run_stats_crawl(
        config,
        # 0 = 전체 페이지(run_stats_crawl은 None을 "제한 없음"으로 해석)
        max_pages=args.max_pages or None,
        out_dir=args.output_dir,
        resume=args.resume,
        start_page=args.start_page,
    )

    print(f"run_id={summary.run_id}")
    print(f"stats_collected={summary.stats_count}")
    print(f"aborted={summary.aborted} reason={summary.abort_reason}")


if __name__ == "__main__":
    main()
