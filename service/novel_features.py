"""작품 정적 필드 + 회차 피처 결합.

누수 방지 원칙: 유료작에서 무료 시기와 유료 시기를 분리할 수 없는 지표는 피처로 쓰지
않는다. 상세는 docs/04_로드맵.md의 핵심 결정 사항 참고.
"""

from __future__ import annotations

import pandas as pd

# 범주형 인코딩은 여기서 하지 않는다 — 모델 파이프라인의 ColumnTransformer에 위임.
# genres는 쉼표로 이어붙인 다중 라벨 문자열이라 조합 그대로 one-hot하면 안 된다
# (학습 121종/추론 316종, 추론셋 15.5%가 미학습 조합). 파이프라인에서 쉼표로 쪼개
# 토큰 단위 multi-hot으로 인코딩한다 — 토큰 기준으로는 학습 17종이 추론 21종에 모두 포함된다.
STATIC_COLUMNS = ["genres"]

# 정적 필드 중 피처에서 제외하는 것과 그 이유:
#   serialization_status — 학습셋(pl.serial_end)은 "완결" 100%, 추론셋(nv.free)은
#     "연재중" 100%로 train/inference 분할과 완전히 교락돼 있다. 학습 시에는 상수라
#     정보량이 0이고, 추론 시에는 학습에서 본 적 없는 카테고리가 들어온다.
#   tags — 조합 3,659종에 결측률이 학습 56.2% vs 추론 35.0%로 서로 달라 결측 자체가
#     또 하나의 covariate shift다. 상위 K개 토큰 multi-hot으로 재검토할 여지는 있다.
EXCLUDED_STATIC_COLUMNS = ["tags", "serialization_status"]

# 피처에서 제외하는 컬럼과 그 이유:
#   total_view_count / chapter_count — 유료작에서는 무료+유료 기간의 누적치라 타겟과
#     누수 관계다. 앞 N화 조회수(free_views_1_N)가 누수 없는 대체재다.
#   like_count / preference_count    — nv.free 크롤에서 73.9%가 결측이고, 유료작에서는
#     위와 같은 누수 문제가 있다.
#   NovelStats의 good_count / prefer_count — 목록 API의 "현재 시점" 스냅샷이라
#     유료작의 무료 시기 값만 분리해낼 수 없다.
LEAKY_COLUMNS = ["total_view_count", "chapter_count", "like_count", "preference_count"]


def build_novel_features(
    novels_df: pd.DataFrame, episode_features_df: pd.DataFrame
) -> pd.DataFrame:
    """작품 정적 필드에 회차 피처를 inner join한다.

    회차 피처가 없는 작품(앞 N화를 확보하지 못한 작품)은 자동으로 빠진다.
    """
    available = [column for column in STATIC_COLUMNS if column in novels_df.columns]
    static = novels_df[["novel_id", *available]]
    return static.merge(episode_features_df, on="novel_id", how="inner")
