"""문피아 무료 자유연재 목록/상세 메타데이터 크롤러 진입점.

사용된 API 엔드포인트는 공식 문서가 없는 비공식/역공학 경로이므로,
본격적인 대량 크롤링에 앞서 반드시 아래처럼 소규모로 먼저 실행하고
data/raw/ 에 생성된 CSV를 눈으로 확인해야 한다.

    uv run python scripts/crawl_munpia.py --max-pages 1 --novel-limit 5
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawler.config import CrawlConfig  # noqa: E402
from clawler.runner import run_crawl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="문피아 무료 연재작 메타데이터 크롤러")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1,
        help="목록 페이지 최대 크롤링 수 (기본 1, 안전을 위한 기본값)",
    )
    parser.add_argument(
        "--novel-limit",
        type=int,
        default=10,
        help="상세정보를 수집할 최대 작품 수 (기본 10)",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = CrawlConfig.from_env()
    if args.delay is not None:
        config = CrawlConfig(**{**config.__dict__, "request_delay_seconds": args.delay})

    summary = run_crawl(
        config,
        max_pages=args.max_pages,
        novel_limit=args.novel_limit,
        out_dir=args.output_dir,
        resume=args.resume,
    )

    print(f"run_id={summary.run_id}")
    print(f"novels_collected={summary.novel_count}")
    print(f"episodes_collected={summary.episode_count}")
    print(f"skipped_novel_ids={summary.skipped_novel_ids}")
    print(f"aborted={summary.aborted} reason={summary.abort_reason}")


if __name__ == "__main__":
    main()
