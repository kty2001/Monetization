from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from entity._mapping import _first


@dataclass
class NovelStats:
    novel_id: str
    section: str
    entry_count: int | None
    comment_count: int | None
    score: float | None
    purchased_count: int | None
    rented_count: int | None
    hit_count: int | None
    good_count: int | None
    prefer_count: int | None
    char_count: int | None
    genre_main: str | None
    genre_sub: str | None
    is_finished: bool | None
    is_adult: bool | None
    is_exclusive: bool | None
    crawled_at: str
    run_id: str

    @classmethod
    def from_list_item(
        cls,
        item: dict[str, Any],
        *,
        section: str,
        crawled_at: datetime,
        run_id: str,
    ) -> "NovelStats":
        return cls(
            novel_id=str(_first(item, ("nvSrl",))),
            section=section,
            entry_count=_first(item, ("nvSumEntry",)),
            comment_count=_first(item, ("nvSumComment",)),
            score=_first(item, ("nvSumScore",)),
            purchased_count=_first(item, ("nvSumPurchased",)),
            rented_count=_first(item, ("nvSumRented",)),
            hit_count=_first(item, ("nvSumHit",)),
            good_count=_first(item, ("nvSumGood",)),
            prefer_count=_first(item, ("nvSumPrefer",)),
            char_count=_first(item, ("nvSumChar",)),
            genre_main=_first(item, ("nvGnMain",)),
            genre_sub=_first(item, ("nvGnSub",)),
            is_finished=_as_bool(_first(item, ("nvOptFinish",))),
            is_adult=_as_bool(_first(item, ("nvOptAdult",))),
            is_exclusive=_as_bool(_first(item, ("nvOptExclusive",))),
            crawled_at=crawled_at.isoformat(),
            run_id=run_id,
        )

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(int(value)) if isinstance(value, str) and value.isdigit() else bool(value)
