"""모델 파이프라인 스모크 테스트.

작은 합성 데이터로 fit→predict가 끝까지 돌고, log1p 역변환이 원공간으로 돌아오며,
학습에서 보지 못한 장르 토큰이 들어와도 죽지 않는지 확인한다.
"""

from __future__ import annotations

import pickle

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

from service.model_training import (
    BAND_NORMAL,
    BAND_SPARSE_HIGH,
    BAND_SPARSE_LOW,
    build_pipeline,
    evaluate,
    genre_tokens,
    median_baseline,
    single_feature_baseline,
    split_xy,
    stratified_split,
    support_band,
    support_bounds,
)
from service.schema import CATEGORICAL_FEATURE_COLUMNS, NUMERIC_FEATURE_COLUMNS
from service.target_builder import TARGET_COLUMN

_GENRES = ["판타지,퓨전", "현대판타지", "무협", "판타지"]


def _frame(rows: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    views = rng.integers(100, 500_000, rows)
    data = {
        CATEGORICAL_FEATURE_COLUMNS[0]: [_GENRES[i % len(_GENRES)] for i in range(rows)],
        NUMERIC_FEATURE_COLUMNS[0]: views,
        NUMERIC_FEATURE_COLUMNS[1]: rng.random(rows),
        NUMERIC_FEATURE_COLUMNS[2]: rng.random(rows),
        NUMERIC_FEATURE_COLUMNS[3]: rng.integers(0, 5_000, rows),
        NUMERIC_FEATURE_COLUMNS[4]: rng.integers(0, 500, rows),
        # 타겟을 조회수에 느슨하게 연동시켜 순위상관이 의미를 갖게 한다.
        TARGET_COLUMN: (views * rng.uniform(0.5, 2.0, rows)).astype(int) + 1,
    }
    return pd.DataFrame(data)


def test_genre_tokens_splits_and_tolerates_missing():
    assert genre_tokens("판타지,퓨전") == ["판타지", "퓨전"]
    assert genre_tokens(" 무협 , 게임 ") == ["무협", "게임"]
    # 결측(NaN)이 들어와도 CountVectorizer가 죽지 않아야 한다.
    assert genre_tokens(np.nan) == []


def test_pipeline_fits_and_predicts_in_original_space():
    X, y = split_xy(_frame())
    model = build_pipeline(HistGradientBoostingRegressor(max_iter=20, random_state=0))
    model.fit(X, y)
    pred = model.predict(X)

    assert len(pred) == len(y)
    # log1p 학습 → expm1 역변환이므로 예측은 원공간(수만~수십만) 스케일이어야 한다.
    assert pred.min() > 0
    assert np.median(pred) > 100


def test_pipeline_handles_nan_in_retention_for_linear_model():
    """retention 컬럼의 NaN(1화 조회수 0)이 Ridge 경로에서 대치되는지."""
    df = _frame()
    df.loc[:5, NUMERIC_FEATURE_COLUMNS[1]] = np.nan
    X, y = split_xy(df)

    model = build_pipeline(Ridge(), impute_log_scale=True)
    model.fit(X, y)

    assert np.isfinite(model.predict(X)).all()


def test_pipeline_survives_unseen_genre_token():
    """추론셋에는 학습셋에 없는 장르 토큰이 있다(21종 vs 17종). 무시되기만 하면 된다."""
    X, y = split_xy(_frame())
    model = build_pipeline(HistGradientBoostingRegressor(max_iter=20, random_state=0))
    model.fit(X, y)

    unseen = X.head(3).copy()
    unseen[CATEGORICAL_FEATURE_COLUMNS[0]] = "라이트노벨,대체역사"
    assert np.isfinite(model.predict(unseen)).all()


def test_fitted_pipeline_is_picklable():
    """joblib을 도입하지 않고 표준 pickle로 직렬화한다 — analyzer가 람다면 여기서 깨진다."""
    X, y = split_xy(_frame())
    model = build_pipeline(HistGradientBoostingRegressor(max_iter=20, random_state=0))
    model.fit(X, y)

    restored = pickle.loads(pickle.dumps(model))
    np.testing.assert_allclose(restored.predict(X), model.predict(X))


def test_evaluate_reports_log_and_original_space_metrics():
    y_true = pd.Series([100, 1_000, 10_000, 100_000])
    perfect = evaluate(y_true, y_true.to_numpy(dtype=float))

    assert perfect["log_rmse"] == pytest.approx(0.0)
    assert perfect["log_r2"] == pytest.approx(1.0)
    assert perfect["mae"] == pytest.approx(0.0)
    assert perfect["mdape"] == pytest.approx(0.0)
    assert perfect["spearman"] == pytest.approx(1.0)


def test_evaluate_returns_nan_spearman_for_constant_prediction():
    """중앙값 베이스라인은 예측이 상수라 순위상관이 정의되지 않는다(경고 대신 NaN)."""
    y_true = pd.Series([100, 1_000, 10_000, 100_000])
    metrics = evaluate(y_true, median_baseline(y_true, len(y_true)))

    assert np.isnan(metrics["spearman"])
    assert np.isfinite(metrics["log_rmse"])


def test_stratified_split_preserves_target_spread():
    X, y = split_xy(_frame(200))
    split = stratified_split(X, y)

    assert len(split.X_train) + len(split.X_test) == len(X)
    # 층화 덕에 고액 구간이 한쪽으로 쏠리지 않아야 한다.
    assert split.y_test.max() > y.median()


def test_single_feature_baseline_tracks_views():
    X, y = split_xy(_frame(120))
    split = stratified_split(X, y)
    pred = single_feature_baseline(split.X_train, split.y_train, split.X_test)

    assert len(pred) == len(split.X_test)
    assert np.isfinite(pred).all()


def test_support_band_labels_by_training_quantiles():
    train = pd.Series(range(1_000, 101_000, 1_000))
    bounds = support_bounds(train)
    labels = support_band(pd.Series([10, bounds.lower + 1, 10_000_000]), bounds)

    assert list(labels) == [BAND_SPARSE_LOW, BAND_NORMAL, BAND_SPARSE_HIGH]
