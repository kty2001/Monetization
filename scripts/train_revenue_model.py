"""구매수 예측 모델 학습 + 저장.

    uv run python scripts/train_revenue_model.py

베이스라인(중앙값 / free_views_1_10 단일회귀)과 후보 모델을 같은 분할에서 비교하고,
로그공간 CV RMSE가 가장 낮은 모델을 전체 학습셋에 다시 적합시켜 저장한다.

⚠️ 예측값은 "유료 전환에 **성공했을 때의** 조건부 기댓값"이다. 학습셋이 전환 성공작만이라
전환 자체의 확률은 모델링하지 않는다(docs/04_로드맵.md 선택 편향 항목).
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.base import clone  # noqa: E402
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor  # noqa: E402
from sklearn.linear_model import ElasticNet, Ridge  # noqa: E402

from service.model_training import (  # noqa: E402
    PROCESSED_DIR,
    build_pipeline,
    cross_validate_model,
    evaluate,
    load_dataset,
    median_baseline,
    single_feature_baseline,
    split_xy,
    stratified_split,
    support_bounds,
)
from service.schema import NUMERIC_FEATURE_COLUMNS  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")

# 두 번째 값은 impute_log_scale — 결측을 네이티브로 못 다루는 모델에만 붙인다.
CANDIDATES = {
    "ridge": (Ridge(alpha=1.0), True),
    "elasticnet": (ElasticNet(alpha=0.01, l1_ratio=0.5, max_iter=5000), True),
    "random_forest": (
        RandomForestRegressor(n_estimators=300, min_samples_leaf=2, random_state=42, n_jobs=-1),
        True,
    ),
    "hist_gbr": (HistGradientBoostingRegressor(random_state=42), False),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="구매수 예측 모델 학습")
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument(
        "--only", nargs="*", choices=list(CANDIDATES), help="일부 후보만 학습(기본: 전체)"
    )
    return parser.parse_args()


def _pipeline_for(name: str):
    """후보 정의에서 매번 새 파이프라인을 만든다(추정기 인스턴스 공유 방지)."""
    estimator, impute_log_scale = CANDIDATES[name]
    return build_pipeline(clone(estimator), impute_log_scale=impute_log_scale)


def _format(name: str, metrics: dict[str, float]) -> str:
    return (
        f"  {name:<22s} logRMSE {metrics['log_rmse']:.4f}  logR2 {metrics['log_r2']:+.4f}  "
        f"MdAPE {metrics['mdape']:6.1f}%  Spearman {metrics['spearman']:+.4f}"
    )


def main() -> None:
    args = parse_args()

    df = load_dataset("labeled")
    X, y = split_xy(df)
    split = stratified_split(X, y)
    print(f"학습셋 {len(df):,}건 → train {len(split.X_train):,} / test {len(split.X_test):,}")

    results: dict[str, dict[str, float]] = {}

    print("\n[베이스라인] (test)")
    results["baseline_median"] = evaluate(
        split.y_test, median_baseline(split.y_train, len(split.y_test))
    )
    print(_format("중앙값", results["baseline_median"]))
    results["baseline_views"] = evaluate(
        split.y_test, single_feature_baseline(split.X_train, split.y_train, split.X_test)
    )
    print(_format(f"{NUMERIC_FEATURE_COLUMNS[0]} 단일회귀", results["baseline_views"]))

    selected = args.only or list(CANDIDATES)
    print(f"\n[후보 모델] {args.folds}-fold CV(train) + holdout(test)")
    for name in selected:
        model = _pipeline_for(name)

        cv_scores = cross_validate_model(model, split.X_train, split.y_train, folds=args.folds)
        model.fit(split.X_train, split.y_train)
        test_scores = evaluate(split.y_test, model.predict(split.X_test))

        results[name] = {**test_scores, **cv_scores}
        print(
            _format(name, test_scores)
            + f"  | CV logRMSE {cv_scores['cv_log_rmse']:.4f} ±{cv_scores['cv_log_rmse_std']:.4f}"
        )

    best = min(selected, key=lambda name: results[name]["cv_log_rmse"])
    baseline_rmse = results["baseline_views"]["log_rmse"]
    gain = (baseline_rmse - results[best]["log_rmse"]) / baseline_rmse * 100
    print(f"\n선택: {best} (단일회귀 베이스라인 대비 logRMSE {gain:+.1f}%)")

    # 선택된 모델을 전체 학습셋에 다시 적합시킨다(holdout은 비교용으로만 썼다).
    final = _pipeline_for(best)
    final.fit(X, y)

    snapshot_date = datetime.now(_KST).strftime("%Y%m%d")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    model_path = args.output_dir / f"revenue_model_{snapshot_date}.pkl"
    with model_path.open("wb") as handle:
        pickle.dump(
            {
                "model": final,
                "model_name": best,
                "support_bounds": support_bounds(X[NUMERIC_FEATURE_COLUMNS[0]]),
                "trained_at": datetime.now(_KST).isoformat(),
                "training_rows": len(df),
            },
            handle,
        )

    metrics_path = args.output_dir / f"model_metrics_{snapshot_date}.json"
    metrics_path.write_text(
        json.dumps({"best": best, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"저장: {model_path}")
    print(f"저장: {metrics_path}")


if __name__ == "__main__":
    main()
