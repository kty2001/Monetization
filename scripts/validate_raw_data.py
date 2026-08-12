"""data/raw/ 의 최신 크롤 결과 CSV(novels/episodes/novel_stats)에 대한 기본 무결성 검증.

    uv run python scripts/validate_raw_data.py
    uv run python scripts/validate_raw_data.py --prefix paid_

novels/episodes는 반드시 같은 run_id 쌍으로 검증한다(서로 다른 run을 섞으면
참조 무결성 검사가 무의미해지므로). novel_stats는 본 크롤과 run_id·디렉토리가
분리돼 있어 --stats-dir에서 따로 찾아 검증한다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from service.data_quality import (  # noqa: E402
    ValidationIssue,
    find_latest_csv,
    run_id_from_path,
    validate_episodes,
    validate_novel_stats,
    validate_novels,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="크롤 결과 CSV 무결성 검증")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--stats-dir",
        type=Path,
        default=Path("data/raw/stats"),
        help="novel_stats_*.csv 디렉토리 (기본 data/raw/stats)",
    )
    parser.add_argument("--prefix", default="", help="파일명 접두사 (예: paid_)")
    return parser.parse_args()


def _print_issues(label: str, row_count: int, issues: list[ValidationIssue]) -> None:
    print(f"\n[{label}] {row_count}행")
    if not issues:
        print("  이상 없음")
        return
    for issue in issues:
        print(f"  [{issue.level.upper()}] {issue.message} (count={issue.count})")


def main() -> None:
    args = parse_args()

    novels_path = find_latest_csv(args.data_dir, "novels", prefix=args.prefix)

    if novels_path is None:
        print(f"'{args.data_dir}'에서 {args.prefix}novels_*.csv 파일을 찾지 못했습니다.")
        sys.exit(1)

    # episodes는 mtime이 아니라 novels와 같은 run_id로 짝지어 고른다.
    run_id = run_id_from_path(novels_path, "novels", prefix=args.prefix)
    episodes_path = args.data_dir / f"{args.prefix}episodes_{run_id}.csv"
    print(f"run_id={run_id}")

    novels_df = pd.read_csv(novels_path)
    novel_issues = validate_novels(novels_df)
    _print_issues(novels_path.name, len(novels_df), novel_issues)

    all_issues = list(novel_issues)

    if episodes_path.exists():
        episodes_df = pd.read_csv(episodes_path)
        episode_issues = validate_episodes(episodes_df, novels_df=novels_df)
        _print_issues(episodes_path.name, len(episodes_df), episode_issues)
        all_issues.extend(episode_issues)
    else:
        print(f"\n'{episodes_path}' 파일이 없습니다(같은 run_id의 episodes CSV).")

    stats_path = find_latest_csv(args.stats_dir, "novel_stats", prefix=args.prefix)
    if stats_path is not None:
        stats_df = pd.read_csv(stats_path)
        stats_issues = validate_novel_stats(stats_df, novels_df=novels_df)
        _print_issues(stats_path.name, len(stats_df), stats_issues)
        all_issues.extend(stats_issues)
    else:
        print(f"\n'{args.stats_dir}'에서 {args.prefix}novel_stats_*.csv 파일을 찾지 못했습니다.")

    error_count = sum(1 for issue in all_issues if issue.level == "error")
    print(f"\n총 {len(all_issues)}건 이슈 (error {error_count}건)")
    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
