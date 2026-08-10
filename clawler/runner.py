from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clawler.config import CrawlConfig
from clawler.detail_crawler import fetch_novel_bundle
from clawler.http_client import BlockedByServerError, MunpiaHttpClient
from clawler.list_crawler import fetch_novel_ids
from entity.episode import Episode
from entity.novel import Novel
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
) -> CrawlSummary:
    run_id = datetime.now(_KST).strftime("%Y%m%d_%H%M%S")
    crawled_at = datetime.now(_KST)
    client = MunpiaHttpClient(config)
    repository = CrawlRepository(run_id=run_id, base_dir=out_dir)
    summary = CrawlSummary(run_id=run_id)

    novels: list[Novel] = []
    episodes: list[Episode] = []

    novel_ids = fetch_novel_ids(client, max_pages=max_pages)
    if novel_limit is not None:
        novel_ids = novel_ids[:novel_limit]

    try:
        for novel_id in novel_ids:
            bundle = fetch_novel_bundle(client, novel_id, crawled_at, run_id)
            if bundle is None:
                summary.skipped_novel_ids.append(novel_id)
                continue
            novel, novel_episodes = bundle
            novels.append(novel)
            episodes.extend(novel_episodes)
    except BlockedByServerError as exc:
        logger.error("Crawl aborted: %s", exc)
        summary.aborted = True
        summary.abort_reason = str(exc)

    if novels:
        repository.save_novels(novels)
    if episodes:
        repository.save_episodes(episodes)

    summary.novel_count = len(novels)
    summary.episode_count = len(episodes)
    return summary
