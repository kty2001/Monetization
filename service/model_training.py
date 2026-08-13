"""구매수 예측 모델의 학습 파이프라인.

노트북(`research/`)과 스크립트(`scripts/train_revenue_model.py`)가 공통으로 쓴다 —
노트북에는 로직을 두지 않고 여기를 호출만 한다.

설계 근거는 docs/04_로드맵.md의 "핵심 결정 사항"과 "C. 모델링" 참고. 요약:

- 타겟(`target_paid_events`)이 3자릿수~8자릿수에 걸쳐 있어 **log1p 공간에서 학습**하고
  `expm1`로 되돌린다(`TransformedTargetRegressor`).
- `genres`는 쉼표로 이어붙인 다중 라벨이라 조합 그대로 one-hot하면 추론셋의 15.5%가
  미학습 조합이 된다. **토큰 단위 multi-hot**으로 인코딩한다.
- 다운스트림이 "작품 순위 매기기"이므로 Spearman 순위상관을 함께 본다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from service.data_quality import find_latest_csv
from service.schema import CATEGORICAL_FEATURE_COLUMNS, ID_COLUMN, NUMERIC_FEATURE_COLUMNS
from service.target_builder import TARGET_COLUMN

# 저장소 루트 기준으로 잡는다 — research/ 노트북은 cwd가 research/라 상대 경로면 깨진다.
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

#: 지지구간 밴드를 가르는 학습셋 분위수. 로드맵 "선택 편향 + 지지구간 불일치" 참고.
SUPPORT_LOWER_QUANTILE = 0.05
SUPPORT_UPPER_QUANTILE = 0.95

BAND_NORMAL = "정상"
BAND_SPARSE_LOW = "희박(하한 미만)"
BAND_SPARSE_HIGH = "희박(상한 초과)"

_RANDOM_STATE = 42
_STRATIFY_BINS = 10


# ── 데이터 로드 ──────────────────────────────────────────────────────────────


def load_dataset(kind: str, base_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    """`data/processed/{kind}_dataset_{snapshot_date}.csv` 중 가장 최근 파일을 로드한다.

    kind: "labeled"(학습셋) 또는 "free"(추론셋).
    """
    if kind not in {"labeled", "free"}:
        raise ValueError(f"kind는 'labeled' 또는 'free'여야 합니다 (받은 값: {kind})")

    path = find_latest_csv(base_dir, f"{kind}_dataset")
    if path is None:
        raise FileNotFoundError(
            f"'{base_dir}'에서 {kind}_dataset_*.csv를 찾지 못했습니다. "
            "scripts/build_processed_dataset.py를 먼저 실행하세요."
        )
    return pd.read_csv(path, dtype={ID_COLUMN: str})


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """피처 프레임과 타겟 시리즈로 나눈다."""
    features = CATEGORICAL_FEATURE_COLUMNS + NUMERIC_FEATURE_COLUMNS
    return df[features], df[TARGET_COLUMN]


# ── 파이프라인 ───────────────────────────────────────────────────────────────


def genre_tokens(text: Any) -> list[str]:
    """쉼표로 이어붙인 장르 문자열을 토큰 리스트로 쪼갠다.

    `CountVectorizer(analyzer=...)`에 넘기므로 **모듈 수준 함수여야 한다** —
    람다로 두면 표준 pickle로 모델을 직렬화할 때 깨진다.
    """
    if not isinstance(text, str):
        return []
    return [token.strip() for token in text.split(",") if token.strip()]


def build_pipeline(
    estimator: Any, *, impute_log_scale: bool = False
) -> TransformedTargetRegressor:
    """전처리 + 추정기를 log1p 타겟 변환으로 감싼 파이프라인을 만든다.

    impute_log_scale: 결측을 네이티브로 다루지 못하는 모델(Ridge/ElasticNet/RandomForest)에
        **중앙값 대치 → log1p → 표준화**를 붙인다. `HistGradientBoostingRegressor`는 NaN을
        그대로 처리하고 단조 변환에 불변이므로 False로 둔다(`retention_*`에 1화 조회수가
        0인 작품의 NaN이 있다).

        log1p가 필요한 이유: `free_views_1_10`/`likes_1_10`/`comments_1_10`이 3~7자릿수에
        걸쳐 극단적으로 치우쳐 있어, 원공간 그대로 선형 모델에 넣으면 로그공간에서 학습되는
        타겟과 스케일이 맞지 않는다. 실제로 log1p 없이는 Ridge가 `free_views_1_10` 하나짜리
        로그-로그 단일회귀 베이스라인보다도 나빴다(logRMSE 1.226 vs 1.111).
    """
    numeric_steps = (
        Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                ("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one")),
                ("scale", StandardScaler()),
            ]
        )
        if impute_log_scale
        else "passthrough"
    )

    preprocessor = ColumnTransformer(
        [
            # 컬럼명을 리스트가 아니라 문자열로 넘겨야 1-D로 전달돼 CountVectorizer가 받는다.
            (
                "genres",
                CountVectorizer(analyzer=genre_tokens, binary=True),
                CATEGORICAL_FEATURE_COLUMNS[0],
            ),
            ("numeric", numeric_steps, NUMERIC_FEATURE_COLUMNS),
        ],
        remainder="drop",
    )

    return TransformedTargetRegressor(
        regressor=Pipeline([("prep", preprocessor), ("model", estimator)]),
        func=np.log1p,
        inverse_func=np.expm1,
    )


# ── 분할 / 교차검증 ──────────────────────────────────────────────────────────


class Split(NamedTuple):
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series


def stratified_split(
    X: pd.DataFrame, y: pd.Series, test_size: float = 0.2, random_state: int = _RANDOM_STATE
) -> Split:
    """타겟 분위수로 층화한 train/test 분할.

    타겟이 4자릿수 스팬에 걸쳐 있어 무작위 분할만으로는 고액 구간이 한쪽으로 쏠린다.
    """
    strata = pd.qcut(y, _STRATIFY_BINS, labels=False, duplicates="drop")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=strata
    )
    return Split(X_train, X_test, y_train, y_test)


def cross_validate_model(
    model: Any, X: pd.DataFrame, y: pd.Series, folds: int = 5
) -> dict[str, float]:
    """K-fold 교차검증. 폴드별 `evaluate` 지표의 평균과 로그 RMSE 표준편차를 반환한다.

    `cross_validate`의 scoring을 쓰지 않는 이유: 예측은 `expm1`로 원공간에 되돌아오므로
    표준 scorer는 원공간 RMSE만 준다. 모델 비교는 로그공간에서 해야 해서 폴드별 예측을
    직접 받아 지표를 낸다.
    """
    splitter = KFold(n_splits=folds, shuffle=True, random_state=_RANDOM_STATE)
    per_fold = []
    for train_idx, test_idx in splitter.split(X):
        fitted = clone(model)
        fitted.fit(X.iloc[train_idx], y.iloc[train_idx])
        per_fold.append(evaluate(y.iloc[test_idx], fitted.predict(X.iloc[test_idx])))

    scores = {f"cv_{key}": float(np.mean([f[key] for f in per_fold])) for key in per_fold[0]}
    scores["cv_log_rmse_std"] = float(np.std([f["log_rmse"] for f in per_fold]))
    return scores


# ── 평가 ────────────────────────────────────────────────────────────────────


def _log_rmse(y_true: pd.Series, y_pred: np.ndarray) -> float:
    true_log = np.log1p(np.asarray(y_true, dtype=float))
    pred_log = np.log1p(np.clip(np.asarray(y_pred, dtype=float), 0, None))
    return float(np.sqrt(np.mean((true_log - pred_log) ** 2)))


def evaluate(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """로그공간·원공간 지표를 함께 낸다.

    - 로그공간 RMSE/R²: 모델 간 비교용(학습이 이 공간에서 이뤄진다)
    - 원공간 MAE/MdAPE: 실제 오차 감각
    - Spearman: 다운스트림이 "순위 매기기"이므로 순위 보존력을 본다
    """
    true = np.asarray(y_true, dtype=float)
    pred = np.clip(np.asarray(y_pred, dtype=float), 0, None)

    true_log, pred_log = np.log1p(true), np.log1p(pred)
    residual_ss = float(np.sum((true_log - pred_log) ** 2))
    total_ss = float(np.sum((true_log - true_log.mean()) ** 2))

    # 타겟은 build_target에서 0 이하를 제외하므로 나눗셈이 안전하다.
    abs_pct_error = np.abs(pred - true) / true

    # 중앙값 베이스라인처럼 예측이 상수면 순위상관이 정의되지 않는다(경고 대신 NaN).
    spearman = (
        float("nan")
        if len(np.unique(pred)) < 2
        else float(pd.Series(pred).corr(pd.Series(true), method="spearman"))
    )

    return {
        "log_rmse": _log_rmse(y_true, y_pred),
        "log_r2": 1.0 - residual_ss / total_ss if total_ss else float("nan"),
        "mae": float(np.mean(np.abs(pred - true))),
        "mdape": float(np.median(abs_pct_error) * 100),
        "spearman": spearman,
    }


# ── 베이스라인 ───────────────────────────────────────────────────────────────


def median_baseline(y_train: pd.Series, n: int) -> np.ndarray:
    """학습셋 중앙값을 그대로 내놓는 예측기."""
    return np.full(n, float(y_train.median()))


def single_feature_baseline(
    X_train: pd.DataFrame, y_train: pd.Series, X_test: pd.DataFrame
) -> np.ndarray:
    """`free_views_1_10` 하나로 하는 로그-로그 단일 회귀.

    "앞 10화 조회수만 봐도 이 정도는 맞힌다"는 하한선. 모델이 이걸 유의미하게 못 이기면
    피처 엔지니어링이나 데이터를 의심해야 한다(로드맵 C절의 DL 검토 판정 기준).
    """
    column = NUMERIC_FEATURE_COLUMNS[0]
    slope, intercept = np.polyfit(np.log1p(X_train[column]), np.log1p(y_train), 1)
    return np.expm1(intercept + slope * np.log1p(X_test[column]))


# ── 지지구간 밴드 ────────────────────────────────────────────────────────────


class SupportBounds(NamedTuple):
    lower: float
    upper: float


def support_bounds(train_values: pd.Series) -> SupportBounds:
    return SupportBounds(
        lower=float(train_values.quantile(SUPPORT_LOWER_QUANTILE)),
        upper=float(train_values.quantile(SUPPORT_UPPER_QUANTILE)),
    )


def support_band(values: pd.Series, bounds: SupportBounds) -> pd.Series:
    """예측값의 신뢰도 밴드를 라벨링한다.

    학습셋 min~max 범위로는 추론셋의 99.4%가 안에 들어와 걸러지지 않지만, 밀도로 보면
    무료작의 84%가 학습셋 5분위수 미만이다. 범위가 아니라 **분위수**로 갈라야 "학습
    데이터가 희박한 구간"을 대시보드에서 구분해 표시할 수 있다(로드맵 핵심 결정 사항).
    """
    return pd.Series(
        np.where(
            values < bounds.lower,
            BAND_SPARSE_LOW,
            np.where(values > bounds.upper, BAND_SPARSE_HIGH, BAND_NORMAL),
        ),
        index=values.index,
        dtype="object",
    )
