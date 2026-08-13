"""무료/유료 데이터셋과 추론 스크립트가 공통으로 쓰는 피처 스키마.

학습 시점과 추론 시점의 피처 목록·순서가 어긋나면 모델이 조용히 엉뚱한 값을 예측한다.
데이터셋을 저장하기 전에 항상 `assert_feature_schema`를 통과시킨다.
"""

from __future__ import annotations

import pandas as pd

from service.episode_features import DEFAULT_N, feature_columns
from service.novel_features import STATIC_COLUMNS
from service.target_builder import TARGET_COLUMN

ID_COLUMN = "novel_id"

#: 모델에 들어가는 수치형 피처 (앞 N화 기준)
NUMERIC_FEATURE_COLUMNS = feature_columns(DEFAULT_N)

#: 범주형 피처 (인코딩은 모델 파이프라인의 ColumnTransformer가 담당)
CATEGORICAL_FEATURE_COLUMNS = list(STATIC_COLUMNS)

FEATURE_COLUMNS = CATEGORICAL_FEATURE_COLUMNS + NUMERIC_FEATURE_COLUMNS

#: 피처는 아니지만 데이터셋에 함께 싣는 컬럼 (진단·조인용)
METADATA_COLUMNS = [ID_COLUMN, "leading_free_episodes"]


class FeatureSchemaError(ValueError):
    """데이터셋 컬럼이 FEATURE_COLUMNS와 어긋날 때 발생."""


def expected_columns(*, with_target: bool) -> list[str]:
    columns = METADATA_COLUMNS + FEATURE_COLUMNS
    return columns + [TARGET_COLUMN] if with_target else columns


def assert_feature_schema(df: pd.DataFrame, *, with_target: bool = False) -> None:
    """컬럼 누락과 예상 밖 컬럼을 **모두** 검출한다."""
    expected = expected_columns(with_target=with_target)
    actual = list(df.columns)

    missing = [column for column in expected if column not in actual]
    unexpected = [column for column in actual if column not in expected]

    if missing or unexpected:
        raise FeatureSchemaError(
            f"피처 스키마 불일치 — 누락: {missing or '없음'} / 예상 밖: {unexpected or '없음'}. "
            f"기대: {expected}"
        )
