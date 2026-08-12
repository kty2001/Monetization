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
from clawler.list_crawler import iter_list_pages
from repository.crawl_repository import CrawlRepository

logger = logging.getLogger(__name__)

_KST = ZoneInfo("Asia/Seoul")


@dataclass
class CrawlSummary:
    run_id: str
    novel_count: int = 0
    episode_count: int = 0
    skipped_novel_ids: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None


def run_crawl(
    config: CrawlConfig,
    max_pages: int | None,
    novel_limit: int | None,
    out_dir: Path = Path("data/raw"),
    resume: bool = False,
) -> CrawlSummary:
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
    repository = CrawlRepository(run_id=run_id, base_dir=out_dir)
    summary = CrawlSummary(run_id=run_id)

    processed_count = 0
    limit_reached = False
    try:
        for novel_ids in iter_list_pages(client, max_pages=max_pages):
            if limit_reached:
                break
            for novel_id in novel_ids:
                if checkpoint.is_done(novel_id):
                    continue
                if novel_limit is not None and processed_count >= novel_limit:
                    limit_reached = True
                    break

                crawled_at = datetime.now(_KST)
                bundle = fetch_novel_bundle(client, novel_id, crawled_at, run_id)
                if bundle is None:
                    summary.skipped_novel_ids.append(novel_id)
                else:
                    novel, episodes = bundle
                    repository.append_novel(novel)
                    if episodes:
                        repository.append_episodes(episodes)
                    summary.novel_count += 1
                    summary.episode_count += len(episodes)

                checkpoint.mark_done(novel_id)
                processed_count += 1
    except (BlockedByServerError, ForbiddenPathError) as exc:
        logger.error("Crawl aborted: %s", exc)
        summary.aborted = True
        summary.abort_reason = str(exc)

    return summary
