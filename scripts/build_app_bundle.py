"""데스크톱 앱과 함께 배포할 번들을 만든다.

    uv run python scripts/build_app_bundle.py

`app/bundle/`에 세 파일을 만든다:

    catalog.csv   조회용 스냅샷 (예측값 + 제목/작가/장르)
    model.pkl     실시간 분석용 모델 (train_revenue_model.py 산출물 복사)
    meta.json     스냅샷 날짜·모델명·학습 건수 (앱 화면에 표기)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from service.data_quality import find_latest_csv  # noqa: E402
from service.episode_features import DEFAULT_N  # noqa: E402
from service.inference import CATALOG_COLUMNS  # noqa: E402
from service.model_training import PROCESSED_DIR  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_DIR = ROOT / "app" / "bundle"

# 작가가 입력한 제목에 U+FEFF(BOM 문자)가 섞여 있는 경우가 있다 — 파일 손상이 아니라
# 원본 문자열이다(docs/03_크롤러.md 조사 결과). 화면에 그대로 뿌리면 깨져 보인다.
_ZERO_WIDTH = "﻿​"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="데스크톱 앱 번들 생성")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--processed-dir", type=Path, default=PROCESSED_DIR)
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR)
    return parser.parse_args()


def _clean_text(series: pd.Series) -> pd.Series:
    return series.fillna("").str.strip(_ZERO_WIDTH).str.strip()


def _latest(directory: Path, pattern: str) -> Path:
    candidates = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"'{directory}'에서 {pattern}을(를) 찾지 못했습니다.")
    return candidates[-1]


def main() -> None:
    args = parse_args()

    predictions_path = _latest(args.processed_dir, "predictions_*.csv")
    model_path = _latest(args.processed_dir, "revenue_model_*.pkl")
    novels_path = find_latest_csv(args.raw_dir, "novels")
    if novels_path is None:
        raise FileNotFoundError(f"'{args.raw_dir}'에서 novels_*.csv를 찾지 못했습니다.")

    predictions = pd.read_csv(predictions_path, dtype={"novel_id": str})
    novels = pd.read_csv(
        novels_path,
        dtype={"novel_id": str},
        usecols=["novel_id", "title", "author", "genres", "crawled_at"],
    ).drop_duplicates("novel_id")

    # 앱이 "어느 범위에서 검색하는지"를 화면에 정확히 쓰려면 크롤 시점과 원본 규모가 필요하다.
    # 예측을 돌린 날짜(파일명)를 수집 시점으로 표시하면 틀린 정보가 된다.
    crawled_at = pd.to_datetime(novels["crawled_at"], format="mixed", utc=True).dt.tz_convert(
        "Asia/Seoul"
    )
    source_total = len(novels)
    novels = novels.drop(columns=["crawled_at"])

    catalog = predictions.merge(novels, on="novel_id", how="left")
    missing_title = int(catalog["title"].isna().sum())
    catalog["title"] = _clean_text(catalog["title"])
    catalog["author"] = _clean_text(catalog["author"])
    catalog["genres"] = _clean_text(catalog["genres"])
    catalog = catalog[CATALOG_COLUMNS].sort_values(
        "predicted_paid_events_per_episode", ascending=False, ignore_index=True
    )

    args.bundle_dir.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(args.bundle_dir / "catalog.csv", index=False, encoding="utf-8-sig")
    shutil.copyfile(model_path, args.bundle_dir / "model.pkl")

    meta = {
        # 크롤 시점과 예측 시점은 다르다. 둘을 섞으면 앱이 잘못된 수집 시점을 표시한다.
        "crawl_start": crawled_at.min().strftime("%Y-%m-%d"),
        "crawl_end": crawled_at.max().strftime("%Y-%m-%d"),
        "prediction_date": predictions_path.stem.removeprefix("predictions_"),
        # 화면에는 작가가 아는 말로, 추적용 섹션 코드는 별도 키로 남긴다.
        "section": "무료 자유연재",
        "section_code": "nv.free",
        "source_total": source_total,
        "catalog_rows": len(catalog),
        "min_free_episodes": DEFAULT_N,
        "model_file": model_path.name,
    }
    (args.bundle_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"카탈로그: {predictions_path.name} + {novels_path.name} → {len(catalog):,}행")
    print(
        f"  범위:   {meta['section']} {source_total:,}건 "
        f"({meta['crawl_start']}~{meta['crawl_end']} 수집) 중 무료 {DEFAULT_N}화 이상"
    )
    if missing_title:
        print(f"  경고:   제목을 찾지 못한 작품 {missing_title:,}건 (빈 문자열로 저장)")
    print(f"모델:     {model_path.name}")
    print(f"저장:     {args.bundle_dir}")


if __name__ == "__main__":
    main()
