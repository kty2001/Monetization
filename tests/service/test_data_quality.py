import os

import pandas as pd

from service.data_quality import (
    check_duplicates,
    check_missing_rate,
    check_referential_integrity,
    check_value_ranges,
    find_latest_csv,
    validate_episodes,
    validate_novels,
)


def test_find_latest_csv_picks_prefix_and_most_recent(tmp_path):
    older = tmp_path / "novels_20260101_000000.csv"
    older.write_text("a")
    os.utime(older, (1000, 1000))

    newer = tmp_path / "novels_20260102_000000.csv"
    newer.write_text("a")
    os.utime(newer, (2000, 2000))

    paid = tmp_path / "paid_novels_20260103_000000.csv"
    paid.write_text("a")
    os.utime(paid, (3000, 3000))

    result = find_latest_csv(tmp_path, "novels")

    assert result == newer


def test_find_latest_csv_returns_none_when_missing(tmp_path):
    assert find_latest_csv(tmp_path, "novels") is None


def test_check_duplicates_detects_duplicate_key():
    df = pd.DataFrame({"novel_id": [1, 2, 2]})

    issue = check_duplicates(df, "novel_id")

    assert issue is not None
    assert issue.level == "error"
    assert issue.count == 1


def test_check_duplicates_returns_none_when_unique():
    df = pd.DataFrame({"novel_id": [1, 2, 3]})

    assert check_duplicates(df, "novel_id") is None


def test_check_missing_rate_flags_column_above_threshold():
    df = pd.DataFrame({"title": ["A", None, None, None]})

    issues = check_missing_rate(df, ["title"], threshold=0.3)

    assert len(issues) == 1
    assert issues[0].level == "warning"
    assert issues[0].count == 3


def test_check_missing_rate_ignores_column_below_threshold():
    df = pd.DataFrame({"title": ["A", "B", "C", None]})

    issues = check_missing_rate(df, ["title"], threshold=0.3)

    assert issues == []


def test_check_value_ranges_detects_negative_values():
    df = pd.DataFrame({"view_count": [10, -5, 0]})

    issues = check_value_ranges(df, ["view_count"])

    assert len(issues) == 1
    assert issues[0].count == 1


def test_check_referential_integrity_detects_orphan_episodes():
    novels_df = pd.DataFrame({"novel_id": [1, 2]})
    episodes_df = pd.DataFrame({"novel_id": [1, 1, 3]})

    issue = check_referential_integrity(episodes_df, novels_df)

    assert issue is not None
    assert issue.count == 1


def test_check_referential_integrity_returns_none_when_consistent():
    novels_df = pd.DataFrame({"novel_id": [1, 2]})
    episodes_df = pd.DataFrame({"novel_id": [1, 2]})

    assert check_referential_integrity(episodes_df, novels_df) is None


def test_validate_novels_combines_checks():
    df = pd.DataFrame(
        {
            "novel_id": [1, 1],
            "title": ["A", "B"],
            "author": ["X", "Y"],
            "genres": ["로맨스", "판타지"],
            "chapter_count": [10, -1],
            "total_view_count": [100, 200],
        }
    )

    issues = validate_novels(df)

    assert any(issue.level == "error" for issue in issues)


def test_validate_episodes_combines_checks():
    novels_df = pd.DataFrame({"novel_id": [1]})
    episodes_df = pd.DataFrame(
        {
            "episode_id": [1, 2],
            "novel_id": [1, 99],
            "title": ["1화", "2화"],
            "published_at": ["2026-01-01", "2026-01-02"],
            "view_count": [10, 5],
            "like_count": [1, 0],
            "comment_count": [0, 0],
            "order_index": [1, 2],
        }
    )

    issues = validate_episodes(episodes_df, novels_df=novels_df)

    assert any("고아" in issue.message for issue in issues)
