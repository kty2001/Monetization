"""data/raw/ → data/processed/ 데이터셋 생성.

    # 추론셋(무료작, 타겟 없음)
    uv run python scripts/build_processed_dataset.py --free

    # 학습셋(유료 전환작, 타겟 포함)
    uv run python scripts/build_processed_dataset.py --labeled \
        --data-dir data/raw/paid --stats-dir data/raw/paid --prefix paid_

출력은 run_id가 아니라 snapshot_date(YYYYMMDD)로 누적 저장한다(덮어쓰지 않음).
여러 시점 데이터를 모아 시계열 피처를 만들기 위한 것.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from service.episode_features import DEFAULT_N, compute_episode_features  # noqa: E402
from service.novel_features import build_novel_features  # noqa: E402
from service.raw_loader import load_crawl_dataset, load_stats  # noqa: E402
from service.schema import assert_feature_schema, expected_columns  # noqa: E402
from service.target_builder import (  # noqa: E402
    TARGET_COLUMN,
    build_target,
    paid_episode_counts,
)

_KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="가공 데이터셋 생성")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--free", action="store_true", help="추론셋(무료작, 타겟 없음)")
    mode.add_argument("--labeled", action="store_true", help="학습셋(유료 전환작, 타겟 포함)")

    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--stats-dir", type=Path, default=Path("data/raw/stats"))
    parser.add_argument("--prefix", default="", help="파일명 접두사 (예: paid_)")
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--n-episodes", type=int, default=DEFAULT_N, help=f"앞 N화 기준 (기본 {DEFAULT_N})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    labeled = bool(args.labeled)

    dataset = load_crawl_dataset(args.data_dir, prefix=args.prefix)
    print(f"run_id={dataset.run_id}  작품 {len(dataset.novels)}건 / 회차 {len(dataset.episodes)}건")

    episode_features = compute_episode_features(dataset.episodes, n=args.n_episodes)
    dropped_short = len(dataset.novels) - len(episode_features)
    print(f"앞 {args.n_episodes}화 확보: {len(episode_features)}건 (미달로 제외 {dropped_short}건)")

    frame = build_novel_features(dataset.novels, episode_features)

    if labeled:
        stats = load_stats(args.stats_dir, prefix=args.prefix)
        # 타겟은 회차당 구매수다 — 총 구매수를 유료 회차 수로 나눈다(상세는 target_builder).
        episodes_per_novel = paid_episode_counts(dataset.novels, dataset.episodes)
        target = build_target(stats, episodes_per_novel)
        print(
            f"타겟 확보: {len(target.frame)}건 "
            f"(구매수 0/결측·회차수 불명으로 제외 {target.dropped_count}건)"
        )
        print(f"  유료 회차 수 중앙값: {episodes_per_novel.median():.0f}화")
        frame = frame.merge(target.frame, on="novel_id", how="inner")

    frame = frame[expected_columns(with_target=labeled)]
    assert_feature_schema(frame, with_target=labeled)

    snapshot_date = datetime.now(_KST).strftime("%Y%m%d")
    name = "labeled" if labeled else "free"
    out_path = args.output_dir / f"{name}_dataset_{snapshot_date}.csv"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_path, index=False, encoding="utf-8-sig")

    print(f"\n저장: {out_path}  ({len(frame)}행 × {len(frame.columns)}컬럼)")
    if labeled:
        described = frame[TARGET_COLUMN].describe()
        print(
            f"타겟(회차당 구매수) 분포: 중앙값 {described['50%']:.0f} / "
            f"최대 {described['max']:.0f}"
        )
    if not len(frame):
        print("경고: 행이 0건입니다. --data-dir/--prefix가 맞는지 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
