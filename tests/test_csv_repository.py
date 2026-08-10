from datetime import datetime

import pandas as pd

from entity.episode import Episode
from entity.novel import Novel
from repository.crawl_repository import CrawlRepository

CRAWLED_AT = datetime(2026, 1, 1, 12, 0, 0)
RUN_ID = "20260101_120000"


def test_save_novels_writes_expected_csv(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path)
    novel = Novel.from_api_response(
        {"novelId": 1, "title": "A"}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    path = repository.save_novels([novel])

    assert path == tmp_path / f"novels_{RUN_ID}.csv"
    assert path.exists()
    df = pd.read_csv(path)
    assert df.loc[0, "novel_id"] == 1
    assert df.loc[0, "title"] == "A"


def test_save_episodes_writes_expected_csv(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path)
    episode = Episode.from_api_response(
        {"episodeId": 1, "title": "1화"},
        novel_id="1",
        crawled_at=CRAWLED_AT,
        run_id=RUN_ID,
    )

    path = repository.save_episodes([episode])

    assert path == tmp_path / f"episodes_{RUN_ID}.csv"
    df = pd.read_csv(path)
    assert df.loc[0, "episode_id"] == 1
    assert df.loc[0, "novel_id"] == 1
