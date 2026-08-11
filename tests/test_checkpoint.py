import time

from clawler.checkpoint import CrawlCheckpoint


def test_new_checkpoint_starts_empty(tmp_path):
    checkpoint = CrawlCheckpoint(run_id="20260101_000000", base_dir=tmp_path)

    assert not checkpoint.is_done("1")
    assert checkpoint.processed_novel_ids == set()


def test_mark_done_persists_across_reload(tmp_path):
    run_id = "20260101_000000"
    checkpoint = CrawlCheckpoint(run_id=run_id, base_dir=tmp_path)
    checkpoint.mark_done("1")
    checkpoint.mark_done("2")

    reloaded = CrawlCheckpoint(run_id=run_id, base_dir=tmp_path)

    assert reloaded.is_done("1")
    assert reloaded.is_done("2")
    assert not reloaded.is_done("3")


def test_find_latest_returns_none_when_no_checkpoint(tmp_path):
    assert CrawlCheckpoint.find_latest(tmp_path) is None


def test_find_latest_picks_most_recently_modified(tmp_path):
    older = CrawlCheckpoint(run_id="20260101_000000", base_dir=tmp_path)
    older.mark_done("1")
    time.sleep(0.01)
    newer = CrawlCheckpoint(run_id="20260102_000000", base_dir=tmp_path)
    newer.mark_done("2")

    latest = CrawlCheckpoint.find_latest(tmp_path)

    assert latest is not None
    assert latest.run_id == "20260102_000000"
    assert latest.is_done("2")
