from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clawler.checkpoint import CrawlCheckpoint
from clawler.config import CrawlConfig
from clawler.detail_crawler import fetch_novel_bundle
from clawler.http_client import BlockedByServerError, ForbiddenPathError, MunpiaHttpClient
from clawler.list_crawler import iter_list_page_items
from entity.novel_stats import NovelStats
from repository.crawl_repository import CrawlRepository

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


@dataclass
class CrawlSummary:
    run_id: str
    novel_count: int = 0
    episode_count: int = 0
    stats_count: int = 0
    skipped_novel_ids: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None


def run_crawl(
    config: CrawlConfig,
    max_pages: int | None,
    novel_limit: int | None,
    out_dir: Path = Path("data/raw"),
    resume: bool = False,
    prefix: str = "",
    collect_stats: bool = False,
    start_page: int = 1,
    free_chapters_only: bool = False,
) -> CrawlSummary:
    """목록 → 작품 상세 → 회차를 순회하며 CSV에 즉시 append한다.

    prefix: 출력 파일명 접두사(예: "paid_"). 무료/유료 크롤 결과를 분리한다.
    collect_stats: 목록 item에서 NovelStats(구매수 등)도 함께 저장한다. 유료 섹션
        (pl.serial/pl.serial_end)의 타겟인 nvSumPurchased가 목록 API에만 있으므로,
        같은 순회에서 타겟과 피처를 한 번에 얻기 위한 옵션.

    start_page: 목록 시작 페이지. --resume만으로 재개하면 앞 페이지를 전부 재스캔해
        페이지당 딜레이가 그대로 드므로, 중단 지점 근처부터 시작할 때 쓴다.
    free_chapters_only: 첫 유료 회차에서 회차 수집을 중단한다(유료 섹션 크롤용).
        상세는 fetch_novel_bundle의 docstring 참고.

    out_dir는 성격이 다른 크롤끼리 반드시 분리할 것. CrawlCheckpoint.find_latest가
    디렉토리 안의 체크포인트를 mtime으로만 고르기 때문에, 같은 디렉토리를 쓰면
    --resume이 엉뚱한 체크포인트를 집는다.
    """
    checkpoint = CrawlCheckpoint.find_latest(out_dir) if resume else None
    if checkpoint is None:
        run_id = datetime.now(_KST).strftime("%Y%m%d_%H%M%S")
        checkpoint = CrawlCheckpoint(run_id=run_id, base_dir=out_dir)
    else:
        run_id = checkpoint.run_id
        logger.info(
            "Resuming run_id=%s (%d novels already processed, will re-skip on rescan)",
            run_id,
            len(checkpoint.processed_novel_ids),
        )

    client = MunpiaHttpClient(config)
    repository = CrawlRepository(run_id=run_id, base_dir=out_dir, prefix=prefix)
    summary = CrawlSummary(run_id=run_id)

    processed_count = 0
    limit_reached = False
    try:
        for items in iter_list_page_items(client, max_pages=max_pages, start_page=start_page):
            if limit_reached:
                break
            for item in items:
                novel_id = str(item["nvSrl"])
                if checkpoint.is_done(novel_id):
                    continue
                if novel_limit is not None and processed_count >= novel_limit:
                    limit_reached = True
                    break

                crawled_at = datetime.now(_KST)
                bundle = fetch_novel_bundle(
                    client,
                    novel_id,
                    crawled_at,
                    run_id,
                    free_chapters_only=free_chapters_only,
                )
                if bundle is None:
                    summary.skipped_novel_ids.append(novel_id)
                else:
                    novel, episodes = bundle
                    repository.append_novel(novel)
                    if episodes:
                        repository.append_episodes(episodes)
                    summary.novel_count += 1
                    summary.episode_count += len(episodes)

                if collect_stats:
                    # 상세 수집에 실패(bundle is None)해도 목록 item은 유효하므로
                    # 타겟(구매수)은 남긴다. novels에 없는 stats row가 생길 수 있고,
                    # validate_raw_data.py의 커버리지 검사가 warning으로 보고한다.
                    repository.append_stats(
                        [
                            NovelStats.from_list_item(
                                item,
                                section=config.section,
                                crawled_at=crawled_at,
                                run_id=run_id,
                            )
                        ]
                    )
                    summary.stats_count += 1

                checkpoint.mark_done(novel_id)
                processed_count += 1
    except (BlockedByServerError, ForbiddenPathError) as exc:
        logger.error("Crawl aborted: %s", exc)
        summary.aborted = True
        summary.abort_reason = str(exc)

    return summary
