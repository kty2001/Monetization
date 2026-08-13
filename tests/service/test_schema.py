import pandas as pd
import pytest

from service.novel_features import EXCLUDED_STATIC_COLUMNS
from service.schema import (
    FEATURE_COLUMNS,
    FeatureSchemaError,
    assert_feature_schema,
    expected_columns,
)


def _frame(with_target: bool = False) -> pd.DataFrame:
    return pd.DataFrame(columns=expected_columns(with_target=with_target))


def test_assert_feature_schema_accepts_expected_columns():
    assert_feature_schema(_frame())
    assert_feature_schema(_frame(with_target=True), with_target=True)


def test_assert_feature_schema_detects_missing_column():
    df = _frame().drop(columns=["retention_1_to_10"])

    with pytest.raises(FeatureSchemaError, match="retention_1_to_10"):
        assert_feature_schema(df)


def test_assert_feature_schema_detects_unexpected_column():
    df = _frame()
    df["total_view_count"] = []  # 누수 컬럼이 실수로 섞여 들어온 상황

    with pytest.raises(FeatureSchemaError, match="total_view_count"):
        assert_feature_schema(df)


def test_degenerate_categoricals_stay_out_of_features():
    """학습/추론 분할과 교락된 범주형이 피처로 되돌아오는 것을 막는다.

    serialization_status는 학습셋 "완결" 100% / 추론셋 "연재중" 100%이고, tags는
    결측률이 양쪽에서 다르다. 상세는 service/novel_features.py 주석 참고.
    """
    for column in EXCLUDED_STATIC_COLUMNS:
        assert column not in FEATURE_COLUMNS


def test_assert_feature_schema_requires_target_only_when_asked():
    # 타겟이 있는데 with_target=False면 "예상 밖" 컬럼으로 잡혀야 한다.
    with pytest.raises(FeatureSchemaError, match="target_paid_events"):
        assert_feature_schema(_frame(with_target=True))

    # 타겟이 없는데 with_target=True면 "누락"으로 잡혀야 한다.
    with pytest.raises(FeatureSchemaError, match="target_paid_events"):
        assert_feature_schema(_frame(), with_target=True)
