from __future__ import annotations

from pathlib import Path

from entity.episode import Episode
from entity.novel import Novel
from repository.csv_writer import write_csv


class CrawlRepository:
    def __init__(self, run_id: str, base_dir: Path = Path("data/raw")) -> None:
        self.run_id = run_id
        self.base_dir = base_dir

    def save_novels(self, novels: list[Novel]) -> Path:
        path = self.base_dir / f"novels_{self.run_id}.csv"
        write_csv([novel.to_row() for novel in novels], path)
        return path

    def save_episodes(self, episodes: list[Episode]) -> Path:
        path = self.base_dir / f"episodes_{self.run_id}.csv"
        write_csv([episode.to_row() for episode in episodes], path)
        return path
