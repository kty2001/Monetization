from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clawler.checkpoint import CrawlCheckpoint
from clawler.config import CrawlConfig
from clawler.http_client import BlockedByServerError, ForbiddenPathError, MunpiaHttpClient
from clawler.list_crawler import iter_list_page_items
from entity.novel_stats import NovelStats
from repository.crawl_repository import CrawlRepository

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


@dataclass
class StatsCrawlSummary:
    run_id: str
    stats_count: int = 0
    aborted: bool = False
    abort_reason: str | None = None


def run_stats_crawl(
    config: CrawlConfig,
    max_pages: int | None,
    out_dir: Path,
    resume: bool = False,
    start_page: int = 1,
) -> StatsCrawlSummary:
    """목록 API만 순회해 NovelStats(좋아요/선호작/댓글 등)를 수집한다.

    작품 상세·회차 호출이 없어 본 크롤(clawler/runner.py)보다 훨씬 저비용이다.
    out_dir는 본 크롤과 겹치지 않는 별도 디렉터리를 쓰는 것을 전제로 한다
    (같은 디렉터리를 쓰면 CrawlCheckpoint.find_latest가 서로 다른 크롤의
    체크포인트 중 가장 최근 것을 집어 충돌할 수 있음).
    """
    checkpoint = CrawlCheckpoint.find_latest(out_dir) if resume else None
    if checkpoint is None:
        run_id = datetime.now(_KST).strftime("%Y%m%d_%H%M%S")
        checkpoint = CrawlCheckpoint(run_id=run_id, base_dir=out_dir)
    else:
        run_id = checkpoint.run_id
        logger.info(
            "Resuming stats run_id=%s (%d novels already processed)",
            run_id,
            len(checkpoint.processed_novel_ids),
        )

    client = MunpiaHttpClient(config)
    repository = CrawlRepository(run_id=run_id, base_dir=out_dir)
    summary = StatsCrawlSummary(run_id=run_id)

    try:
        for items in iter_list_page_items(client, max_pages=max_pages, start_page=start_page):
            for item in items:
                novel_id = str(item["nvSrl"])
                if checkpoint.is_done(novel_id):
                    continue

                crawled_at = datetime.now(_KST)
                stats = NovelStats.from_list_item(
                    item, section=config.section, crawled_at=crawled_at, run_id=run_id
                )
                repository.append_stats([stats])
                summary.stats_count += 1

                checkpoint.mark_done(novel_id)
    except (BlockedByServerError, ForbiddenPathError) as exc:
        logger.error("Stats crawl aborted: %s", exc)
        summary.aborted = True
        summary.abort_reason = str(exc)

    return summary
