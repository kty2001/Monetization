"""data/raw/ 의 최신 크롤 결과 CSV(novels/episodes)에 대한 기본 무결성 검증.

    uv run python scripts/validate_raw_data.py
    uv run python scripts/validate_raw_data.py --prefix paid_
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
    validate_episodes,
    validate_novels,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="크롤 결과 CSV 무결성 검증")
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
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
    episodes_path = find_latest_csv(args.data_dir, "episodes", prefix=args.prefix)

    if novels_path is None:
        print(f"'{args.data_dir}'에서 {args.prefix}novels_*.csv 파일을 찾지 못했습니다.")
        sys.exit(1)

    novels_df = pd.read_csv(novels_path)
    novel_issues = validate_novels(novels_df)
    _print_issues(novels_path.name, len(novels_df), novel_issues)

    all_issues = list(novel_issues)

    if episodes_path is not None:
        episodes_df = pd.read_csv(episodes_path)
        episode_issues = validate_episodes(episodes_df, novels_df=novels_df)
        _print_issues(episodes_path.name, len(episodes_df), episode_issues)
        all_issues.extend(episode_issues)
    else:
        print(f"\n'{args.data_dir}'에서 {args.prefix}episodes_*.csv 파일을 찾지 못했습니다.")

    error_count = sum(1 for issue in all_issues if issue.level == "error")
    print(f"\n총 {len(all_issues)}건 이슈 (error {error_count}건)")
    sys.exit(1 if error_count else 0)


if __name__ == "__main__":
    main()
