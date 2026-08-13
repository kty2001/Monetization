"""문피아 무료 자유연재 목록/상세 메타데이터 크롤러 진입점.

사용된 API 엔드포인트는 공식 문서가 없는 비공식/역공학 경로이므로,
본격적인 대량 크롤링에 앞서 반드시 아래처럼 소규모로 먼저 실행하고
data/raw/ 에 생성된 CSV를 눈으로 확인해야 한다.

    uv run python scripts/crawl_munpia.py --max-pages 1 --novel-limit 5
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawler.config import CrawlConfig  # noqa: E402
from clawler.runner import run_crawl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="문피아 작품 메타데이터 크롤러")
    parser.add_argument(
        "--section",
        default="nv.free",
        help="목록 섹션 (nv.free/pl.serial/pl.serial_end 등, 기본 nv.free)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="출력 파일명 접두사 (예: paid_ → paid_novels_{run_id}.csv)",
    )
    parser.add_argument(
        "--collect-stats",
        action="store_true",
        help="목록 API의 구매수/좋아요 등을 novel_stats CSV로 함께 저장 (유료 섹션의 타겟)",
    )
    parser.add_argument(
        "--free-chapters-only",
        action="store_true",
        help="첫 유료 회차에서 회차 수집 중단 (유료 섹션 크롤 시 요청량을 크게 줄임)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="목록 페이지 최대 크롤링 수 (기본 1, 안전을 위한 기본값). 0이면 전체 페이지",
    )
    parser.add_argument(
        "--novel-limit",
        type=int,
        default=10,
        help="상세정보를 수집할 최대 작품 수 (기본 10). 0이면 제한 없음",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/raw"),
        help="CSV 출력 디렉토리 (기본 data/raw)",
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

    summary = run_crawl(
        config,
        # 0 = 제한 없음(run_crawl은 None을 "제한 없음"으로 해석)
        max_pages=args.max_pages or None,
        novel_limit=args.novel_limit or None,
        out_dir=args.output_dir,
        resume=args.resume,
        prefix=args.prefix,
        collect_stats=args.collect_stats,
        start_page=args.start_page,
        free_chapters_only=args.free_chapters_only,
    )

    print(f"run_id={summary.run_id}")
    print(f"novels_collected={summary.novel_count}")
    print(f"episodes_collected={summary.episode_count}")
    print(f"stats_collected={summary.stats_count}")
    print(f"skipped_count={len(summary.skipped_novel_ids)}")
    print(f"skipped_novel_ids={summary.skipped_novel_ids[:20]}")
    print(f"aborted={summary.aborted} reason={summary.abort_reason}")


if __name__ == "__main__":
    main()
