"""유료 섹션(pl.serial/pl.serial_end) 크롤 결과에서 로드맵의 두 가정을 검증한다.

    uv run python scripts/analyze_paid_sample.py                          # 샘플
    uv run python scripts/analyze_paid_sample.py --data-dir data/raw/paid  # 본 크롤

검증 대상:
  1. 무료 회차가 항상 앞쪽에 연속되는가 → "첫 유료 회차에서 중단" 최적화 채택 가능 여부
  2. 무료 회차 수 분포 → 피처 기준 N("앞 N화") 결정
  3. purchased_count가 실제로 채워지는가 → 타겟(target_paid_events) 정의 유효성
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from service.data_quality import find_latest_csv  # noqa: E402

QUANTILES = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="유료 크롤 결과의 무료 회차 구조 분석")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw/paid_sample"))
    parser.add_argument("--prefix", default="paid_")
    return parser.parse_args()


def _quantile_table(series: pd.Series, label: str) -> str:
    if series.empty:
        return f"  {label}: (데이터 없음)"
    q = series.quantile(QUANTILES)
    body = "  ".join(f"{int(p * 100)}%={q.loc[p]:.1f}" for p in QUANTILES)
    return f"  {label}: n={len(series)}  mean={series.mean():.1f}\n    {body}"


def analyze_contiguity(episodes: pd.DataFrame) -> pd.DataFrame:
    """작품별로 회차를 순서대로 놓고 무료/유료 구조를 요약한다."""
    rows = []
    for novel_id, group in episodes.groupby("novel_id"):
        ordered = group.sort_values("order_index")
        is_free = (ordered["access_type"] == "FREE").tolist()
        total = len(is_free)
        free_count = sum(is_free)

        # 첫 유료 회차 위치(1-based). 전부 무료면 None.
        first_paid = next((i + 1 for i, free in enumerate(is_free) if not free), None)
        # 첫 유료 회차 이후에 무료가 다시 나오면 "연속" 가정 위반.
        violated = first_paid is not None and any(is_free[first_paid:])
        # 최적화를 적용했을 때 실제로 받게 될 회차 수(= 앞쪽 연속 무료 구간 길이)
        leading_free = next((i for i, free in enumerate(is_free) if not free), total)

        rows.append(
            {
                "novel_id": novel_id,
                "total_episodes": total,
                "free_episodes": free_count,
                "leading_free_episodes": leading_free,
                "first_paid_index": first_paid,
                "contiguity_violated": violated,
                "free_ratio": free_count / total if total else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    novels_path = find_latest_csv(args.data_dir, "novels", prefix=args.prefix)
    episodes_path = find_latest_csv(args.data_dir, "episodes", prefix=args.prefix)
    stats_path = find_latest_csv(args.data_dir, "novel_stats", prefix=args.prefix)

    if novels_path is None or episodes_path is None:
        print(f"'{args.data_dir}'에서 {args.prefix}novels/episodes CSV를 찾지 못했습니다.")
        sys.exit(1)

    novels = pd.read_csv(novels_path)
    episodes = pd.read_csv(episodes_path)
    summary = analyze_contiguity(episodes)

    print(f"작품 {len(novels)}건, 회차 {len(episodes)}건 ({novels_path.name})")

    print("\n[1] 무료 회차 연속성 (첫 유료 회차 이후 무료가 다시 나오는가)")
    violated = summary[summary["contiguity_violated"]]
    all_free = summary[summary["first_paid_index"].isna()]
    print(f"  회차가 있는 작품: {len(summary)}건")
    print(f"  전부 무료(유료 회차 없음): {len(all_free)}건")
    print(f"  ** 연속성 위반: {len(violated)}건 **")
    if len(violated):
        print("  → '첫 유료 회차에서 중단' 최적화를 쓰면 무료 회차를 놓친다. 채택 불가.")
        cols = ["novel_id", "total_episodes", "free_episodes", "leading_free_episodes"]
        print(violated[cols].head(10).to_string(index=False))
        lost = summary["free_episodes"] - summary["leading_free_episodes"]
        print(f"  최적화 시 누락될 무료 회차: 총 {int(lost.sum())}개 (작품당 최대 {int(lost.max())}개)")
    else:
        print("  → 무료 회차가 앞쪽에 연속. 최적화 채택 가능.")

    print("\n[2] 무료 회차 수 분포 (피처 기준 N 결정용)")
    print(_quantile_table(summary["free_episodes"], "무료 회차 수"))
    print(_quantile_table(summary["total_episodes"], "총 회차 수"))
    print(_quantile_table(summary["free_ratio"] * 100, "무료 비율(%)"))
    for n in (10, 20, 30, 50):
        covered = (summary["free_episodes"] >= n).mean()
        print(f"    N={n:>3}: 무료 회차가 N개 이상인 작품 {covered:.1%}")

    print("\n[3] 타겟(purchased_count) 유효성")
    if stats_path is None:
        print(f"  {args.prefix}novel_stats_*.csv 없음 — --collect-stats 없이 크롤한 듯합니다.")
    else:
        stats = pd.read_csv(stats_path)
        purchased = stats["purchased_count"].fillna(0)
        print(f"  n={len(stats)}  비-0 작품: {(purchased > 0).sum()}건 ({(purchased > 0).mean():.1%})")
        print(_quantile_table(purchased, "purchased_count"))
        print(_quantile_table(stats["rented_count"].fillna(0), "rented_count(참고, 타겟 미사용)"))

        # 목록 API의 총 회차 수와 실제 수집 회차 수가 맞는지 (수집 누락 탐지)
        merged = stats.merge(
            summary, left_on="novel_id", right_on="novel_id", how="inner"
        )
        if len(merged):
            mismatch = merged[merged["entry_count"] != merged["total_episodes"]]
            print(f"  entry_count vs 실제 수집 회차 수 불일치: {len(mismatch)}/{len(merged)}건")


if __name__ == "__main__":
    main()
