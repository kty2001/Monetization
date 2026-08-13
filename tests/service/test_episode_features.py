import pandas as pd
import pytest

from service.episode_features import compute_episode_features, leading_free_episodes


def _episodes(novel_id: str, access_types: list[str], views: list[int] | None = None):
    n = len(access_types)
    views = views if views is not None else [100] * n
    return pd.DataFrame(
        {
            "novel_id": [novel_id] * n,
            "episode_id": [f"{novel_id}-{i}" for i in range(1, n + 1)],
            "order_index": list(range(1, n + 1)),
            "access_type": access_types,
            "view_count": views,
            "like_count": [1] * n,
            "comment_count": [2] * n,
        }
    )


def test_leading_free_stops_at_first_paid_ignoring_trailing_free():
    # 완결 후기가 마지막 회차에 무료로 붙은 케이스(실제 샘플에서 관측).
    df = _episodes("1", ["FREE"] * 3 + ["PAID"] * 2 + ["FREE"])

    leading = leading_free_episodes(df)

    assert list(leading["order_index"]) == [1, 2, 3]
    assert list(leading["episode_rank"]) == [1, 2, 3]


def test_leading_free_treats_missing_access_type_as_a_break():
    df = _episodes("1", ["FREE", "FREE", None, "FREE"])

    leading = leading_free_episodes(df)

    assert list(leading["order_index"]) == [1, 2]


def test_leading_free_drops_duplicate_order_index():
    df = _episodes("1", ["FREE"] * 3)
    df.loc[2, "order_index"] = 2  # order_index 중복 (48,897건 중 5건 발생)

    leading = leading_free_episodes(df)

    assert list(leading["order_index"]) == [1, 2]


def test_compute_episode_features_aggregates_first_n_episodes():
    views = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 999]
    df = _episodes("1", ["FREE"] * 11, views)

    features = compute_episode_features(df, n=10)

    row = features.iloc[0]
    assert row["novel_id"] == "1"
    assert row["free_views_1_10"] == sum(views[:10])  # 11화(999)는 제외
    assert row["retention_1_to_10"] == pytest.approx(10 / 100)
    assert row["retention_1_to_3"] == pytest.approx(80 / 100)
    assert row["likes_1_10"] == 10
    assert row["comments_1_10"] == 20
    # 앞 10화로 집계하더라도 메타데이터는 **실제** 선행 무료 구간 길이(11)를 담아야 한다.
    # head에서 세면 정의상 항상 n이 되어 정보가 사라진다.
    assert row["leading_free_episodes"] == 11


def test_compute_episode_features_excludes_novels_below_n():
    short = _episodes("1", ["FREE"] * 9)
    ok = _episodes("2", ["FREE"] * 10)

    features = compute_episode_features(pd.concat([short, ok]), n=10)

    assert list(features["novel_id"]) == ["2"]


def test_compute_episode_features_counts_only_leading_free_run_toward_n():
    # 무료 5 + 유료 5 + 무료 5 = FREE가 10개지만 선행 구간은 5개뿐이므로 제외돼야 한다.
    df = _episodes("1", ["FREE"] * 5 + ["PAID"] * 5 + ["FREE"] * 5)

    features = compute_episode_features(df, n=10)

    assert features.empty


def test_compute_episode_features_returns_nan_retention_when_first_view_is_zero():
    views = [0] + [50] * 9
    df = _episodes("1", ["FREE"] * 10, views)

    features = compute_episode_features(df, n=10)

    row = features.iloc[0]
    assert row["free_views_1_10"] == 450
    assert pd.isna(row["retention_1_to_10"])
    assert pd.isna(row["retention_1_to_3"])


def test_compute_episode_features_rejects_n_below_three():
    with pytest.raises(ValueError, match="3 이상"):
        compute_episode_features(_episodes("1", ["FREE"] * 5), n=2)
