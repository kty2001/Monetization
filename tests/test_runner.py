import pandas as pd
import pytest

from clawler import runner as runner_module
from clawler.config import CrawlConfig
from clawler.http_client import BlockedByServerError
from clawler.runner import run_crawl


@pytest.fixture
def fake_crawl(monkeypatch):
    """iter_list_page_items / fetch_novel_bundle / MunpiaHttpClient를 대체해
    네트워크 없이 run_crawl의 오케스트레이션만 검증한다.

    pages는 목록 API 원본 item dict의 페이지 목록이다(novel_id는 nvSrl에서 온다).
    """

    def install(pages, bundles):
        item_pages = [[{"nvSrl": novel_id, "nvSumPurchased": 100} for novel_id in page] for page in pages]
        monkeypatch.setattr(runner_module, "MunpiaHttpClient", lambda config: object())
        monkeypatch.setattr(
            runner_module,
            "iter_list_page_items",
            lambda client, max_pages=None, start_page=1: iter(item_pages),
        )

        fetched: list[str] = []

        def fake_fetch(client, novel_id, crawled_at, run_id, free_chapters_only=False):
            fetched.append(novel_id)
            result = bundles[novel_id]
            if isinstance(result, Exception):
                raise result
            if result is None:
                return None
            novel, episodes = result
            return novel(novel_id, crawled_at, run_id), episodes(novel_id, crawled_at, run_id)

        monkeypatch.setattr(runner_module, "fetch_novel_bundle", fake_fetch)
        return fetched

    return install


def _bundle(episode_count: int):
    from entity.episode import Episode
    from entity.novel import Novel

    def make_novel(novel_id, crawled_at, run_id):
        return Novel.from_api_response(
            {"title": f"작품{novel_id}"}, novel_id=novel_id, crawled_at=crawled_at, run_id=run_id
        )

    def make_episodes(novel_id, crawled_at, run_id):
        return [
            Episode.from_api_response(
                {"id": f"{novel_id}-{i}", "num": i, "free": True},
                novel_id=novel_id,
                crawled_at=crawled_at,
                run_id=run_id,
            )
            for i in range(1, episode_count + 1)
        ]

    return make_novel, make_episodes


def test_run_crawl_writes_novels_and_episodes(tmp_path, fake_crawl):
    fake_crawl([["1", "2"]], {"1": _bundle(2), "2": _bundle(1)})

    summary = run_crawl(CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path)

    assert summary.novel_count == 2
    assert summary.episode_count == 3
    assert not summary.aborted
    novels = pd.read_csv(tmp_path / f"novels_{summary.run_id}.csv")
    episodes = pd.read_csv(tmp_path / f"episodes_{summary.run_id}.csv")
    assert len(novels) == 2
    assert len(episodes) == 3


def test_run_crawl_records_skipped_novels(tmp_path, fake_crawl):
    fake_crawl([["1", "2"]], {"1": _bundle(1), "2": None})

    summary = run_crawl(CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path)

    assert summary.novel_count == 1
    assert summary.skipped_novel_ids == ["2"]
    # skip된 작품도 체크포인트에 기록돼 재개 시 다시 시도하지 않는다.
    checkpoint = (tmp_path / f".processed_novel_ids_{summary.run_id}.log").read_text("utf-8")
    assert checkpoint.split() == ["1", "2"]


def test_run_crawl_honors_novel_limit(tmp_path, fake_crawl):
    fetched = fake_crawl([["1", "2", "3"]], {str(i): _bundle(1) for i in range(1, 4)})

    summary = run_crawl(CrawlConfig(), max_pages=1, novel_limit=2, out_dir=tmp_path)

    assert summary.novel_count == 2
    assert fetched == ["1", "2"]


def test_run_crawl_aborts_on_block_but_keeps_collected_rows(tmp_path, fake_crawl):
    fake_crawl([["1", "2"]], {"1": _bundle(1), "2": BlockedByServerError("429")})

    summary = run_crawl(CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path)

    assert summary.aborted
    assert "429" in summary.abort_reason
    assert summary.novel_count == 1
    assert len(pd.read_csv(tmp_path / f"novels_{summary.run_id}.csv")) == 1


def test_run_crawl_resume_skips_already_processed(tmp_path, fake_crawl):
    fake_crawl([["1", "2"]], {"1": _bundle(1), "2": _bundle(1)})
    first = run_crawl(CrawlConfig(), max_pages=1, novel_limit=1, out_dir=tmp_path)
    assert first.novel_count == 1

    fetched = fake_crawl([["1", "2"]], {"1": _bundle(1), "2": _bundle(1)})
    second = run_crawl(
        CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path, resume=True
    )

    assert second.run_id == first.run_id
    assert fetched == ["2"]  # 1은 체크포인트로 건너뜀
    novels = pd.read_csv(tmp_path / f"novels_{first.run_id}.csv")
    assert len(novels) == 2  # 같은 파일에 이어쓰기, 중복 없음
    assert sorted(novels["novel_id"]) == [1, 2]


def test_run_crawl_prefix_writes_separate_filenames(tmp_path, fake_crawl):
    fake_crawl([["1"]], {"1": _bundle(1)})

    summary = run_crawl(
        CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path, prefix="paid_"
    )

    assert (tmp_path / f"paid_novels_{summary.run_id}.csv").exists()
    assert (tmp_path / f"paid_episodes_{summary.run_id}.csv").exists()
    assert not (tmp_path / f"novels_{summary.run_id}.csv").exists()


def test_run_crawl_collect_stats_writes_target_from_list_item(tmp_path, fake_crawl):
    fake_crawl([["1", "2"]], {"1": _bundle(1), "2": _bundle(1)})

    summary = run_crawl(
        CrawlConfig(section="pl.serial_end"),
        max_pages=1,
        novel_limit=None,
        out_dir=tmp_path,
        prefix="paid_",
        collect_stats=True,
    )

    assert summary.stats_count == 2
    stats = pd.read_csv(tmp_path / f"paid_novel_stats_{summary.run_id}.csv")
    assert len(stats) == 2
    assert list(stats["purchased_count"]) == [100, 100]
    assert set(stats["section"]) == {"pl.serial_end"}


def test_run_crawl_without_collect_stats_writes_no_stats_file(tmp_path, fake_crawl):
    fake_crawl([["1"]], {"1": _bundle(1)})

    summary = run_crawl(CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path)

    assert summary.stats_count == 0
    assert not (tmp_path / f"novel_stats_{summary.run_id}.csv").exists()


def test_run_crawl_collects_stats_even_when_detail_fetch_skipped(tmp_path, fake_crawl):
    # 상세 수집 실패해도 목록 item의 타겟(구매수)은 남긴다.
    fake_crawl([["1"]], {"1": None})

    summary = run_crawl(
        CrawlConfig(), max_pages=1, novel_limit=None, out_dir=tmp_path, collect_stats=True
    )

    assert summary.skipped_novel_ids == ["1"]
    assert summary.novel_count == 0
    assert summary.stats_count == 1
