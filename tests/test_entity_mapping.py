import json
from datetime import datetime
from pathlib import Path

from entity.episode import Episode
from entity.novel import Novel

FIXTURES = Path(__file__).parent / "fixtures"
CRAWLED_AT = datetime(2026, 1, 1, 12, 0, 0)
RUN_ID = "20260101_120000"


def test_novel_from_api_response_maps_known_fields():
    data = json.loads((FIXTURES / "novel_detail_sample.json").read_text(encoding="utf-8"))
    novel_info = data["result"]["novelInfo"]

    novel = Novel.from_api_response(
        novel_info, novel_id="592090", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert novel.novel_id == "592090"
    assert novel.title == "샘플 소설"
    assert novel.author == "홍길동"
    assert novel.genres == "공포·미스테리"
    assert novel.tags == "회귀,복수"
    assert novel.chapter_count == 120
    assert novel.total_view_count == 987654
    assert novel.serialization_status == "연재중"
    assert novel.run_id == RUN_ID


def test_novel_from_api_response_derives_finished_status():
    novel = Novel.from_api_response(
        {"finish": True, "pause": False}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert novel.serialization_status == "완결"


def test_novel_from_api_response_derives_paused_status():
    novel = Novel.from_api_response(
        {"finish": False, "pause": True}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert novel.serialization_status == "연재중단"


def test_novel_from_api_response_handles_missing_fields():
    novel = Novel.from_api_response({}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID)

    assert novel.novel_id == "1"
    assert novel.title is None
    assert novel.genres == ""
    assert novel.chapter_count is None
    assert novel.serialization_status is None


def test_episode_from_api_response_maps_known_fields():
    data = json.loads((FIXTURES / "chapters_sample.json").read_text(encoding="utf-8"))
    item = data["result"]["list"][0]

    episode = Episode.from_api_response(
        item, novel_id="592090", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert episode.novel_id == "592090"
    assert episode.episode_id == "1"
    assert episode.access_type == "FREE"
    assert episode.view_count == 1000
    assert episode.like_count == 10
    assert episode.comment_count == 2
    assert episode.order_index == 1


def test_episode_from_api_response_maps_paid_access_type():
    data = json.loads((FIXTURES / "chapters_sample.json").read_text(encoding="utf-8"))
    item = data["result"]["list"][1]

    episode = Episode.from_api_response(
        item, novel_id="592090", crawled_at=CRAWLED_AT, run_id=RUN_ID
    )

    assert episode.access_type == "PAID"


def test_episode_from_api_response_handles_missing_fields():
    episode = Episode.from_api_response({}, novel_id="1", crawled_at=CRAWLED_AT, run_id=RUN_ID)

    assert episode.title is None
    assert episode.view_count is None
    assert episode.access_type is None
