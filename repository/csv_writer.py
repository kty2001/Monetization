from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def append_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    # utf-8-sig는 매 호출마다 BOM을 앞에 붙이므로, 파일이 이미 있으면
    # BOM 없는 utf-8로 이어써서 파일 중간에 BOM이 섞여 들어가는 것을 방지한다.
    encoding = "utf-8" if file_exists else "utf-8-sig"
    pd.DataFrame(rows).to_csv(path, index=False, encoding=encoding, mode="a", header=not file_exists)
