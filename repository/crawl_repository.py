from __future__ import annotations

from pathlib import Path

from entity.episode import Episode
from entity.novel import Novel
from entity.novel_stats import NovelStats
from repository.csv_writer import append_csv, write_csv


class CrawlRepository:
    def __init__(self, run_id: str, base_dir: Path = Path("data/raw"), prefix: str = "") -> None:
        self.run_id = run_id
        self.base_dir = base_dir
        self.prefix = prefix

    def _novels_path(self) -> Path:
        return self.base_dir / f"{self.prefix}novels_{self.run_id}.csv"

    def _episodes_path(self) -> Path:
        return self.base_dir / f"{self.prefix}episodes_{self.run_id}.csv"

    def _stats_path(self) -> Path:
        return self.base_dir / f"{self.prefix}novel_stats_{self.run_id}.csv"

    def save_novels(self, novels: list[Novel]) -> Path:
        path = self._novels_path()
        write_csv([novel.to_row() for novel in novels], path)
        return path

    def save_episodes(self, episodes: list[Episode]) -> Path:
        path = self._episodes_path()
        write_csv([episode.to_row() for episode in episodes], path)
        return path

    def append_novel(self, novel: Novel) -> Path:
        path = self._novels_path()
        append_csv([novel.to_row()], path)
        return path

    def append_episodes(self, episodes: list[Episode]) -> Path:
        path = self._episodes_path()
        append_csv([episode.to_row() for episode in episodes], path)
        return path

    def save_stats(self, stats: list[NovelStats]) -> Path:
        path = self._stats_path()
        write_csv([stat.to_row() for stat in stats], path)
        return path

    def append_stats(self, stats: list[NovelStats]) -> Path:
        path = self._stats_path()
        append_csv([stat.to_row() for stat in stats], path)
        return path
