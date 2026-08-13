import pandas as pd
import pytest

from service.target_builder import TARGET_COLUMN, build_target, paid_episode_counts


def _paid_episodes(mapping: dict[str, float]) -> pd.Series:
    return pd.Series(mapping, name="paid_episodes")


def test_paid_episode_counts_subtracts_collected_free_chapters():
    """유료 회차는 수집하지 않으므로 총 회차 수에서 무료 회차 수를 빼서 센다."""
    novels = pd.DataFrame({"novel_id": ["1", "2"], "chapter_count": [200, 30]})
    episodes = pd.DataFrame({"novel_id": ["1"] * 25 + ["2"] * 10})

    counts = paid_episode_counts(novels, episodes)

    assert counts["1"] == 175
    assert counts["2"] == 20


def test_paid_episode_counts_floors_at_one():
    """총 회차 수가 어긋나 음수가 나와도 0으로 나누지 않도록 최소 1로 둔다."""
    novels = pd.DataFrame({"novel_id": ["1"], "chapter_count": [5]})
    episodes = pd.DataFrame({"novel_id": ["1"] * 25})

    assert paid_episode_counts(novels, episodes)["1"] == 1


def test_build_target_divides_purchases_by_paid_episodes():
    """nvSumPurchased는 작품 전체 누적치다 — 회차당으로 환산해야 단가를 곱할 수 있다."""
    stats = pd.DataFrame({"novel_id": ["1", "2"], "purchased_count": [70_000, 1_000]})

    result = build_target(stats, _paid_episodes({"1": 175.0, "2": 10.0}))

    assert list(result.frame[TARGET_COLUMN]) == pytest.approx([400.0, 100.0])
    assert result.dropped_count == 0


def test_build_target_drops_zero_and_missing_purchase_counts():
    stats = pd.DataFrame(
        {
            "novel_id": ["1", "2", "3", "4"],
            "purchased_count": [100, 0, None, 250],
        }
    )

    result = build_target(stats, _paid_episodes({"1": 10.0, "2": 10.0, "3": 10.0, "4": 10.0}))

    assert list(result.frame["novel_id"]) == ["1", "4"]
    assert list(result.frame[TARGET_COLUMN]) == pytest.approx([10.0, 25.0])
    assert result.dropped_count == 2


def test_build_target_drops_novels_without_known_episode_count():
    stats = pd.DataFrame({"novel_id": ["1", "2"], "purchased_count": [100, 200]})

    result = build_target(stats, _paid_episodes({"1": 10.0}))

    assert list(result.frame["novel_id"]) == ["1"]
    assert result.dropped_count == 1


def test_build_target_coerces_non_numeric_to_dropped():
    stats = pd.DataFrame({"novel_id": ["1", "2"], "purchased_count": ["abc", "300"]})

    result = build_target(stats, _paid_episodes({"1": 10.0, "2": 10.0}))

    assert list(result.frame["novel_id"]) == ["2"]
    assert list(result.frame[TARGET_COLUMN]) == pytest.approx([30.0])
    assert result.dropped_count == 1


def test_build_target_returns_empty_frame_when_nothing_qualifies():
    # nv.free는 purchased_count가 항상 0이라 학습 타겟이 나오지 않아야 한다.
    stats = pd.DataFrame({"novel_id": ["1", "2"], "purchased_count": [0, 0]})

    result = build_target(stats, _paid_episodes({"1": 10.0, "2": 10.0}))

    assert result.frame.empty
    assert result.dropped_count == 2
    assert list(result.frame.columns) == ["novel_id", TARGET_COLUMN]
