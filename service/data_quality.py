from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

Level = Literal["error", "warning"]

NOVEL_NON_NEGATIVE_COLUMNS = [
    "chapter_count",
    "total_view_count",
    "like_count",
    "preference_count",
]
EPISODE_NON_NEGATIVE_COLUMNS = ["view_count", "like_count", "comment_count", "order_index"]
STATS_NON_NEGATIVE_COLUMNS = [
    "entry_count",
    "comment_count",
    "purchased_count",
    "rented_count",
    "hit_count",
    "good_count",
    "prefer_count",
    "char_count",
]


@dataclass
class ValidationIssue:
    level: Level
    message: str
    count: int = 0


def find_latest_csv(base_dir: Path, name: str, prefix: str = "") -> Path | None:
    """data/raw/{prefix}{name}_{run_id}.csv 패턴에서 가장 최근 수정된 파일을 찾는다."""
    candidates = sorted(
        base_dir.glob(f"{prefix}{name}_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def run_id_from_path(path: Path, name: str, prefix: str = "") -> str:
    """{prefix}{name}_{run_id}.csv 파일명에서 run_id를 추출한다."""
    return path.stem[len(f"{prefix}{name}_") :]


def check_duplicates(df: pd.DataFrame, key: str) -> ValidationIssue | None:
    dup_count = int(df.duplicated(subset=key).sum())
    if dup_count:
        return ValidationIssue("error", f"'{key}' 컬럼에 중복된 값이 있습니다", dup_count)
    return None


def check_missing_rate(
    df: pd.DataFrame, columns: list[str], threshold: float = 0.3
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column in columns:
        if column not in df.columns:
            continue
        rate = df[column].isna().mean()
        if rate > threshold:
            issues.append(
                ValidationIssue(
                    "warning",
                    f"'{column}' 결측 비율이 {rate:.1%}로 임계치({threshold:.0%})를 초과합니다",
                    int(df[column].isna().sum()),
                )
            )
    return issues


def check_value_ranges(df: pd.DataFrame, non_negative_columns: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for column in non_negative_columns:
        if column not in df.columns:
            continue
        negative_count = int((df[column] < 0).sum())
        if negative_count:
            issues.append(ValidationIssue("error", f"'{column}'에 음수 값이 있습니다", negative_count))
    return issues


def check_referential_integrity(
    episodes_df: pd.DataFrame, novels_df: pd.DataFrame
) -> ValidationIssue | None:
    orphan_count = int((~episodes_df["novel_id"].isin(novels_df["novel_id"])).sum())
    if orphan_count:
        return ValidationIssue(
            "error",
            "episodes의 novel_id 중 novels에 없는 값이 있습니다(고아 row)",
            orphan_count,
        )
    return None


def check_novel_id_coverage(
    stats_df: pd.DataFrame, novels_df: pd.DataFrame
) -> list[ValidationIssue]:
    """stats와 novels의 novel_id 교집합 상태를 점검한다.

    목록 API는 크롤 도중에도 정렬 순서가 바뀌므로 양쪽에 소수의 누락이 생길 수
    있다(치명적이지 않아 warning). join 시 피처를 잃는 작품 수를 파악하는 용도.
    """
    issues: list[ValidationIssue] = []
    novel_ids = set(novels_df["novel_id"])
    stats_ids = set(stats_df["novel_id"])

    missing_in_novels = len(stats_ids - novel_ids)
    if missing_in_novels:
        issues.append(
            ValidationIssue(
                "warning",
                "novel_stats의 novel_id 중 novels에 없는 값이 있습니다",
                missing_in_novels,
            )
        )
    missing_in_stats = len(novel_ids - stats_ids)
    if missing_in_stats:
        issues.append(
            ValidationIssue(
                "warning",
                "novels의 novel_id 중 novel_stats에 없는 값이 있습니다(join 시 통계 피처 결측)",
                missing_in_stats,
            )
        )
    return issues


def validate_novels(df: pd.DataFrame) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dup = check_duplicates(df, "novel_id")
    if dup:
        issues.append(dup)
    issues.extend(check_missing_rate(df, ["title", "author", "genres"]))
    issues.extend(check_value_ranges(df, NOVEL_NON_NEGATIVE_COLUMNS))
    return issues


def validate_episodes(
    df: pd.DataFrame, novels_df: pd.DataFrame | None = None
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    dup = check_duplicates(df, "episode_id")
    if dup:
        issues.append(dup)
    issues.extend(check_missing_rate(df, ["title", "published_at"]))
    issues.extend(check_value_ranges(df, EPISODE_NON_NEGATIVE_COLUMNS))
    if novels_df is not None:
        ref = check_referential_integrity(df, novels_df)
        if ref:
            issues.append(ref)
    return issues


def validate_novel_stats(
    df: pd.DataFrame, novels_df: pd.DataFrame | None = None
) -> list[ValidationIssue]:
    """novel_stats_{run_id}.csv 검증. 매출 예측 타겟(purchased_count)의 원천이라
    novels/episodes와 동등하게 점검한다."""
    issues: list[ValidationIssue] = []
    dup = check_duplicates(df, "novel_id")
    if dup:
        issues.append(dup)
    issues.extend(check_missing_rate(df, ["genre_main", "score", "purchased_count"]))
    issues.extend(check_value_ranges(df, STATS_NON_NEGATIVE_COLUMNS))
    if novels_df is not None:
        issues.extend(check_novel_id_coverage(df, novels_df))
    return issues
