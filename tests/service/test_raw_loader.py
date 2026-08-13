import os

import pandas as pd
import pytest

from service.raw_loader import load_crawl_dataset, load_stats


def _write(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def test_load_crawl_dataset_pairs_episodes_by_run_id(tmp_path):
    # 최신 novels는 run B인데 episodes는 run A가 더 최근에 수정된 상황.
    # mtime으로 각각 고르면 서로 다른 run이 섞인다.
    old = tmp_path / "novels_20260101_000000.csv"
    _write(old, [{"novel_id": "1", "title": "A"}])
    os.utime(old, (1000, 1000))

    new = tmp_path / "novels_20260102_000000.csv"
    _write(new, [{"novel_id": "2", "title": "B"}])
    os.utime(new, (2000, 2000))

    ep_new = tmp_path / "episodes_20260102_000000.csv"
    _write(ep_new, [{"novel_id": "2", "episode_id": "2-1"}])
    os.utime(ep_new, (2000, 2000))

    ep_old = tmp_path / "episodes_20260101_000000.csv"
    _write(ep_old, [{"novel_id": "1", "episode_id": "1-1"}])
    os.utime(ep_old, (9000, 9000))  # 가장 최근 수정

    dataset = load_crawl_dataset(tmp_path)

    assert dataset.run_id == "20260102_000000"
    assert list(dataset.novels["novel_id"]) == ["2"]
    assert list(dataset.episodes["episode_id"]) == ["2-1"]


def test_load_crawl_dataset_keeps_novel_id_as_string(tmp_path):
    _write(tmp_path / "novels_20260101_000000.csv", [{"novel_id": 592090, "title": "A"}])
    _write(
        tmp_path / "episodes_20260101_000000.csv",
        [{"novel_id": 592090, "episode_id": 8570107}],
    )

    dataset = load_crawl_dataset(tmp_path)

    assert dataset.novels["novel_id"].iloc[0] == "592090"
    assert dataset.episodes["novel_id"].iloc[0] == "592090"


def test_load_crawl_dataset_raises_when_episodes_run_id_missing(tmp_path):
    _write(tmp_path / "novels_20260101_000000.csv", [{"novel_id": "1"}])
    _write(tmp_path / "episodes_20251231_000000.csv", [{"novel_id": "1"}])

    with pytest.raises(FileNotFoundError, match="episodes_20260101_000000.csv"):
        load_crawl_dataset(tmp_path)


def test_load_crawl_dataset_honors_prefix(tmp_path):
    _write(tmp_path / "novels_20260101_000000.csv", [{"novel_id": "1"}])
    _write(tmp_path / "episodes_20260101_000000.csv", [{"novel_id": "1"}])
    _write(tmp_path / "paid_novels_20260102_000000.csv", [{"novel_id": "9"}])
    _write(tmp_path / "paid_episodes_20260102_000000.csv", [{"novel_id": "9"}])

    dataset = load_crawl_dataset(tmp_path, prefix="paid_")

    assert list(dataset.novels["novel_id"]) == ["9"]


def test_load_stats_raises_with_helpful_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="novel_stats"):
        load_stats(tmp_path)
