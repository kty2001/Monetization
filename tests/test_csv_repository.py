from datetime import datetime

import pandas as pd

from entity.episode import Episode
from entity.novel import Novel
from entity.novel_stats import NovelStats
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


def test_append_novel_accumulates_rows_across_calls(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path)
    novel_a = Novel.from_api_response(
        {"novelId": 1, "title": "A"}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )
    novel_b = Novel.from_api_response(
        {"novelId": 2, "title": "B"}, novel_id="2", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    repository.append_novel(novel_a)
    path = repository.append_novel(novel_b)

    df = pd.read_csv(path)
    assert len(df) == 2
    assert list(df["title"]) == ["A", "B"]
    # 두 번째 append에서 BOM/헤더가 중간에 섞여 들어가지 않았는지 확인
    assert df["novel_id"].dtype.kind in ("i", "u")


def test_append_episodes_accumulates_rows_across_calls(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path)
    ep1 = Episode.from_api_response(
        {"episodeId": 1, "title": "1화"}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )
    ep2 = Episode.from_api_response(
        {"episodeId": 2, "title": "2화"}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    repository.append_episodes([ep1])
    path = repository.append_episodes([ep2])

    df = pd.read_csv(path)
    assert len(df) == 2
    assert list(df["title"]) == ["1화", "2화"]


def test_prefix_option_writes_separate_filenames(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path, prefix="paid_")
    novel = Novel.from_api_response(
        {"novelId": 1, "title": "A"}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    path = repository.save_novels([novel])

    assert path == tmp_path / f"paid_novels_{RUN_ID}.csv"
    assert not (tmp_path / f"novels_{RUN_ID}.csv").exists()


def test_save_and_append_stats_writes_expected_csv(tmp_path):
    repository = CrawlRepository(run_id=RUN_ID, base_dir=tmp_path, prefix="paid_")
    stats = NovelStats.from_list_item(
        {"nvSrl": 1, "nvSumPurchased": 100}, section="pl.serial_end", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    path = repository.save_stats([stats])

    assert path == tmp_path / f"paid_novel_stats_{RUN_ID}.csv"
    df = pd.read_csv(path)
    assert df.loc[0, "purchased_count"] == 100

    stats2 = NovelStats.from_list_item(
        {"nvSrl": 2, "nvSumPurchased": 200}, section="pl.serial_end", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )
    repository.append_stats([stats2])
    df2 = pd.read_csv(path)
    assert len(df2) == 2
