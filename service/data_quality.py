from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

Level = Literal["error", "warning"]

NOVEL_NON_NEGATIVE_COLUMNS = ["chapter_count", "total_view_count"]
EPISODE_NON_NEGATIVE_COLUMNS = ["view_count", "like_count", "comment_count", "order_index"]


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
