"""학습된 모델을 무료작(추론셋)에 적용해 예측 구매수를 낸다.

    uv run python scripts/predict_conversion_revenue.py

출력은 `data/processed/predictions_{snapshot_date}.csv`이고 앱이 이 파일을 읽는다.

예측값은 **회차당 구매 건수**다(작품 전체 누적이 아니다 — `service/target_builder.py` 참고).
전 회차 합계가 필요하면 여기에 유료 연재 회차 수를 곱한다.

⚠️ **매출(KRW) 환산은 여기서 하지 않는다.** 회차 단가가 작가별 계약에 따라 달라 크롤로
확보할 수 없으므로, 앱에서 사용자가 입력한 단가를 곱한다.

⚠️ 예측값은 "유료 전환에 **성공했을 때의** 조건부 기댓값"이다. 학습셋(전환 성공작)과
추론셋(무료작)의 밀도가 크게 어긋나 있어(무료작 84%가 학습셋 5분위수 미만) `support_band`
컬럼으로 신뢰도를 구분해 내보낸다 — 대시보드는 이 값을 반드시 노출해야 한다.
"""

from __future__ import annotations

import argparse
import pickle
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from service.data_quality import find_latest_csv  # noqa: E402
from service.model_training import (  # noqa: E402
    PROCESSED_DIR,
    load_dataset,
    split_xy,
    support_band,
)
from service.schema import CATEGORICAL_FEATURE_COLUMNS, ID_COLUMN, NUMERIC_FEATURE_COLUMNS  # noqa: E402

_KST = ZoneInfo("Asia/Seoul")
PREDICTION_COLUMN = "predicted_paid_events_per_episode"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="무료작 구매수 예측")
    parser.add_argument("--model-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    return parser.parse_args()


def _latest_model(model_dir: Path) -> Path:
    candidates = sorted(model_dir.glob("revenue_model_*.pkl"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(
            f"'{model_dir}'에서 revenue_model_*.pkl을 찾지 못했습니다. "
            "scripts/train_revenue_model.py를 먼저 실행하세요."
        )
    return candidates[-1]


def main() -> None:
    args = parse_args()

    model_path = _latest_model(args.model_dir)
    with model_path.open("rb") as handle:
        artifact = pickle.load(handle)
    print(
        f"모델: {model_path.name} ({artifact['model_name']}, "
        f"학습 {artifact['training_rows']:,}건, {artifact['trained_at'][:10]})"
    )

    df = load_dataset("free")
    # 추론셋에는 타겟이 없으므로 split_xy 대신 피처 컬럼만 직접 고른다.
    X = df[CATEGORICAL_FEATURE_COLUMNS + NUMERIC_FEATURE_COLUMNS]
    print(f"추론 대상 {len(df):,}건 ({find_latest_csv(PROCESSED_DIR, 'free_dataset').name})")

    predictions = artifact["model"].predict(X)
    bounds = artifact["support_bounds"]

    out = pd.DataFrame(
        {
            ID_COLUMN: df[ID_COLUMN],
            PREDICTION_COLUMN: predictions.round().astype("int64"),
            NUMERIC_FEATURE_COLUMNS[0]: df[NUMERIC_FEATURE_COLUMNS[0]],
            "support_band": support_band(df[NUMERIC_FEATURE_COLUMNS[0]], bounds),
        }
    ).sort_values(PREDICTION_COLUMN, ascending=False, ignore_index=True)

    snapshot_date = datetime.now(_KST).strftime("%Y%m%d")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / f"predictions_{snapshot_date}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n지지구간 밴드 (학습셋 {bounds.lower:,.0f} ~ {bounds.upper:,.0f} 기준)")
    counts = out["support_band"].value_counts()
    for band, count in counts.items():
        print(f"  {band:<16s} {count:6,d}건 ({count / len(out) * 100:5.1f}%)")

    described = out[PREDICTION_COLUMN].describe()
    print(
        f"\n예측 회차당 구매수: 중앙값 {described['50%']:,.0f} / 최대 {described['max']:,.0f}"
    )
    print(f"저장: {out_path}  ({len(out):,}행)")


if __name__ == "__main__":
    main()
