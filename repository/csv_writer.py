from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        first_line = f.readline()
    return next(csv.reader([first_line]))


def append_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    df = pd.DataFrame(rows)

    if file_exists:
        existing_columns = _read_header(path)
        if list(df.columns) != existing_columns:
            raise ValueError(
                f"'{path}'의 기존 헤더 {existing_columns}와 새로 쓰려는 컬럼 {list(df.columns)}이 다릅니다. "
                "엔티티 스키마가 바뀐 채로 기존 run_id 파일에 이어쓰려는 것일 수 있습니다 — "
                "새 run_id로 크롤을 시작하거나, 기존 파일을 새 스키마로 마이그레이션한 뒤 다시 시도하세요."
            )

    # utf-8-sig는 매 호출마다 BOM을 앞에 붙이므로, 파일이 이미 있으면
    # BOM 없는 utf-8로 이어써서 파일 중간에 BOM이 섞여 들어가는 것을 방지한다.
    encoding = "utf-8" if file_exists else "utf-8-sig"
    df.to_csv(path, index=False, encoding=encoding, mode="a", header=not file_exists)
