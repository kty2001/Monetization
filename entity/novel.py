from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from entity._mapping import _first, _join_list


def _derive_status(data: dict[str, Any]) -> str | None:
    # 문피아 novel-detail 응답에는 status 문자열이 없고 finish/pause 불리언만 있다.
    if "finish" not in data and "pause" not in data:
        return None
    if data.get("finish"):
        return "완결"
    if data.get("pause"):
        return "연재중단"
    return "연재중"


@dataclass
class Novel:
    novel_id: str
    title: str | None
    author: str | None
    genres: str
    tags: str
    chapter_count: int | None
    total_view_count: int | None
    serialization_status: str | None
    created_at: str | None
    crawled_at: str
    run_id: str

    @classmethod
    def from_api_response(
        cls, data: dict[str, Any], *, novel_id: str, crawled_at: datetime, run_id: str
    ) -> "Novel":
        return cls(
            novel_id=str(_first(data, ("novelId", "novel_id", "id"), novel_id)),
            title=_first(data, ("title", "novelTitle")),
            author=_first(data, ("author", "authorName", "penName")),
            genres=_join_list(_first(data, ("genres", "genre"))),
            tags=_join_list(_first(data, ("tags",))),
            chapter_count=_first(data, ("chapterCount", "chapter_count", "episodeCount")),
            total_view_count=_first(data, ("viewCount", "view_count", "totalViewCount")),
            serialization_status=_first(data, ("status", "serializationStatus")) or _derive_status(data),
            created_at=_first(data, ("createdAt", "created_at", "firstPublishedAt")),
            crawled_at=crawled_at.isoformat(),
            run_id=run_id,
        )

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
