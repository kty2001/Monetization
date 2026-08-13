"""회차 데이터 → 작품 단위 피처.

핵심 원칙: **앞 N화 기준으로만 집계한다.**

학습셋(pl.serial_end)의 무료 회차는 프로모션 티저(중앙값 25화)이고 추론셋(nv.free)의
무료 회차는 작품 전체(중앙값 3화)라, "무료 회차 전체"로 집계하면 같은 피처가 양쪽에서
전혀 다른 것을 의미하게 된다. 앞 N화로 맞춰야 두 데이터셋이 비교 가능해진다.
근거는 docs/04_로드맵.md의 핵심 결정 사항 참고.
"""

from __future__ import annotations

import pandas as pd

DEFAULT_N = 10
_EARLY_RETENTION_AT = 3


def free_views_column(n: int = DEFAULT_N) -> str:
    return f"free_views_1_{n}"


def retention_column(n: int = DEFAULT_N) -> str:
    return f"retention_1_to_{n}"


def likes_column(n: int = DEFAULT_N) -> str:
    return f"likes_1_{n}"


def comments_column(n: int = DEFAULT_N) -> str:
    return f"comments_1_{n}"


EARLY_RETENTION_COLUMN = f"retention_1_to_{_EARLY_RETENTION_AT}"


def feature_columns(n: int = DEFAULT_N) -> list[str]:
    return [
        free_views_column(n),
        retention_column(n),
        EARLY_RETENTION_COLUMN,
        likes_column(n),
        comments_column(n),
    ]


def leading_free_episodes(episodes_df: pd.DataFrame) -> pd.DataFrame:
    """작품별 **선행 연속 무료 구간**의 회차만 남기고, 1부터 시작하는 순번을 붙인다.

    단순히 access_type == "FREE"로 거르면 안 된다 — 완결 후기가 마지막 회차에 무료로
    붙는 경우가 있어(샘플 20건 중 1건 관측) 티저가 아닌 회차가 섞여 들어온다.
    """
    df = episodes_df
    # order_index가 작품 내에서 중복되는 경우가 극소수 있다(48,897건 중 5건).
    df = df.drop_duplicates(subset=["novel_id", "order_index"], keep="first")
    df = df.sort_values(["novel_id", "order_index"], kind="stable")

    # access_type이 결측이면 무료라고 단정할 수 없으므로 구간을 끊는다.
    is_free = df["access_type"].eq("FREE")
    paid_seen = (~is_free).groupby(df["novel_id"]).cumsum()
    leading = df[paid_seen == 0].copy()
    leading["episode_rank"] = leading.groupby("novel_id").cumcount() + 1
    return leading


def compute_episode_features(episodes_df: pd.DataFrame, n: int = DEFAULT_N) -> pd.DataFrame:
    """작품별 앞 n화 집계 피처를 반환한다(novel_id 컬럼 포함).

    선행 연속 무료 구간이 n화 미만인 작품은 **제외**한다(결측으로 채우지 않는다).
    피처를 계산할 근거 자체가 없는 작품이라 추론 대상이 아니기 때문이다.
    """
    if n < _EARLY_RETENTION_AT:
        raise ValueError(f"n은 {_EARLY_RETENTION_AT} 이상이어야 합니다 (받은 값: {n})")

    leading = leading_free_episodes(episodes_df)
    # 앞 n화로 자르기 **전에** 세야 실제 선행 무료 구간 길이가 나온다. head에서 세면
    # 정의상 항상 n이 되어 메타데이터로서 아무 정보도 남지 않는다.
    leading_counts = leading.groupby("novel_id").size()

    head = leading[leading["episode_rank"] <= n]
    counts = head.groupby("novel_id").size()
    eligible = counts[counts == n].index
    head = head[head["novel_id"].isin(eligible)]

    if head.empty:
        # 조건을 만족하는 작품이 없으면 아래 pivot이 컬럼을 만들지 못해 KeyError가 난다.
        return pd.DataFrame(columns=["novel_id", *feature_columns(n), "leading_free_episodes"])

    grouped = head.groupby("novel_id")
    features = pd.DataFrame(
        {
            free_views_column(n): grouped["view_count"].sum(),
            likes_column(n): grouped["like_count"].sum(),
            comments_column(n): grouped["comment_count"].sum(),
        }
    )

    views_at = head.pivot_table(
        index="novel_id", columns="episode_rank", values="view_count", aggfunc="first"
    )
    first_views = views_at[1]
    # 1화 조회수가 0이면 잔존률이 정의되지 않는다(전체 48,897건 중 1건).
    # HistGradientBoostingRegressor가 NaN을 네이티브 처리하므로 채우지 않는다.
    denominator = first_views.replace(0, pd.NA)
    features[retention_column(n)] = views_at[n] / denominator
    features[EARLY_RETENTION_COLUMN] = views_at[_EARLY_RETENTION_AT] / denominator

    # 선행 무료 구간 길이는 피처가 아니라 메타데이터다 — 유료작에서는 플랫폼이 정한
    # 티저 수(≈25 고정), 무료작에서는 작가가 쓴 전체 분량이라 의미가 다르다.
    features["leading_free_episodes"] = leading_counts.reindex(features.index)

    return features.reset_index()[["novel_id", *feature_columns(n), "leading_free_episodes"]]
