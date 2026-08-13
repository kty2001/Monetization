from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pandas as pd

from service.data_quality import find_latest_csv, run_id_from_path

# novel_id를 문자열로 고정한다. CSV에서 읽으면 숫자로 추론돼 novels/episodes/stats를
# join할 때 dtype이 어긋날 수 있다.
_ID_DTYPE = {"novel_id": str, "episode_id": str}


class CrawlDataset(NamedTuple):
    novels: pd.DataFrame
    episodes: pd.DataFrame
    run_id: str


def load_crawl_dataset(data_dir: Path, prefix: str = "") -> CrawlDataset:
    """가장 최근 novels CSV와 **같은 run_id의** episodes CSV를 짝지어 로드한다.

    mtime으로 각각 고르면 서로 다른 run이 섞여 회차-작품 대응이 깨진다
    (scripts/validate_raw_data.py와 같은 방식).
    """
    novels_path = find_latest_csv(data_dir, "novels", prefix=prefix)
    if novels_path is None:
        raise FileNotFoundError(f"'{data_dir}'에서 {prefix}novels_*.csv를 찾지 못했습니다.")

    run_id = run_id_from_path(novels_path, "novels", prefix=prefix)
    episodes_path = data_dir / f"{prefix}episodes_{run_id}.csv"
    if not episodes_path.exists():
        raise FileNotFoundError(
            f"'{episodes_path}'가 없습니다. novels({novels_path.name})와 같은 run_id의 "
            "episodes CSV가 필요합니다."
        )

    return CrawlDataset(
        novels=pd.read_csv(novels_path, dtype=_ID_DTYPE),
        episodes=pd.read_csv(episodes_path, dtype=_ID_DTYPE),
        run_id=run_id,
    )


def load_stats(stats_dir: Path, prefix: str = "") -> pd.DataFrame:
    """가장 최근 novel_stats CSV를 로드한다(본 크롤과 run_id가 다르므로 별도로 찾는다)."""
    stats_path = find_latest_csv(stats_dir, "novel_stats", prefix=prefix)
    if stats_path is None:
        raise FileNotFoundError(f"'{stats_dir}'에서 {prefix}novel_stats_*.csv를 찾지 못했습니다.")
    return pd.read_csv(stats_path, dtype=_ID_DTYPE)
