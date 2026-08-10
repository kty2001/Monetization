from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any

from entity._mapping import _first


def _derive_access_type(data: dict[str, Any]) -> str | None:
    # 문피아 chapters 응답은 accessType 문자열이 아니라 free 불리언으로 표현한다.
    direct = _first(data, ("accessType", "access_type"))
    if direct is not None:
        return direct
    if "free" not in data:
        return None
    return "FREE" if data.get("free") else "PAID"


@dataclass
class Episode:
    novel_id: str
    episode_id: str
    title: str | None
    published_at: str | None
    access_type: str | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    order_index: int | None
    crawled_at: str
    run_id: str

    @classmethod
    def from_api_response(
        cls,
        data: dict[str, Any],
        *,
        novel_id: str,
        crawled_at: datetime,
        run_id: str,
    ) -> "Episode":
        return cls(
            novel_id=novel_id,
            episode_id=str(_first(data, ("episodeId", "episode_id", "id"))),
            title=_first(data, ("title", "episodeTitle")),
            published_at=_first(data, ("publishedAt", "published_at", "createdAt")),
            access_type=_derive_access_type(data),
            view_count=_first(data, ("viewCount", "view_count")),
            like_count=_first(data, ("likeCount", "like_count")),
            comment_count=_first(data, ("commentCount", "comment_count")),
            order_index=_first(data, ("order", "orderIndex", "no", "num")),
            crawled_at=crawled_at.isoformat(),
            run_id=run_id,
        )

    def to_row(self) -> dict[str, Any]:
        return asdict(self)
