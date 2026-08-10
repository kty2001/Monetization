from __future__ import annotations

import logging
from datetime import datetime

from clawler.http_client import BlockedByServerError, MunpiaHttpClient
from entity.episode import Episode
from entity.novel import Novel

logger = logging.getLogger(__name__)


def _unwrap(data: dict, *keys: str) -> dict:
    for key in keys:
        if isinstance(data, dict) and key in data and data[key] is not None:
            data = data[key]
    return data


def fetch_novel_bundle(
    client: MunpiaHttpClient, novel_id: str, crawled_at: datetime, run_id: str
) -> tuple[Novel, list[Episode]] | None:
    try:
        detail_path = client.config.novel_detail_path_template.format(novel_id=novel_id)
        detail_data = client.get_json(detail_path)
        novel_info = _unwrap(detail_data, "result", "novelInfo")
        novel = Novel.from_api_response(
            novel_info, novel_id=novel_id, crawled_at=crawled_at, run_id=run_id
        )

        episodes: list[Episode] = []
        page = 1
        while True:
            chapters_path = client.config.chapters_path_template.format(
                novel_id=novel_id, page=page, size=client.config.chapters_page_size
            )
            chapters_data = client.get_json(chapters_path)
            items = _unwrap(chapters_data, "result", "list")
            if not items:
                break
            for item in items:
                episodes.append(
                    Episode.from_api_response(
                        item, novel_id=novel_id, crawled_at=crawled_at, run_id=run_id
                    )
                )
            if len(items) < client.config.chapters_page_size:
                break
            page += 1

        return novel, episodes
    except BlockedByServerError:
        raise
    except Exception:
        logger.warning("Skipping novel_id=%s due to error", novel_id, exc_info=True)
        return None
