from datetime import datetime

import pytest

from clawler.config import CrawlConfig
from clawler.detail_crawler import _describe, _unwrap, fetch_novel_bundle
from clawler.http_client import BlockedByServerError, ForbiddenPathError

CRAWLED_AT = datetime(2026, 1, 1, 12, 0, 0)
RUN_ID = "20260101_120000"


class FakeClient:
    """get_json 호출을 경로 substring으로 분기하는 가짜 클라이언트."""

    def __init__(self, detail: dict, chapter_pages: list[dict] | None = None):
        self.config = CrawlConfig()
        self.detail = detail
        self.chapter_pages = chapter_pages or [{"result": {"list": []}}]
        self.calls: list[str] = []

    def get_json(self, path: str, params: dict | None = None) -> dict:
        self.calls.append(path)
        if "/chapters" in path:
            index = sum(1 for call in self.calls if "/chapters" in call) - 1
            if index >= len(self.chapter_pages):
                return {"result": {"list": []}}
            page = self.chapter_pages[index]
            if isinstance(page, Exception):
                raise page
            return page
        return self.detail


def _detail(**info) -> dict:
    return {"result": {"novelInfo": {"title": "제목", "authorName": "작가", **info}}}


def _chapter_page(count: int, start: int = 1) -> dict:
    return {
        "result": {
            "list": [
                {"id": start + i, "title": f"{start + i}화", "num": start + i, "free": True}
                for i in range(count)
            ]
        }
    }


def test_unwrap_returns_none_when_path_missing():
    # 예전 구현은 원본 dict를 그대로 돌려줘 스키마 변경을 조용히 넘겼다.
    assert _unwrap({"data": {"items": []}}, "result", "list") is None
    assert _unwrap({"result": {"list": [1, 2]}}, "result", "list") == [1, 2]
    assert _unwrap({"result": None}, "result", "list") is None
    assert _unwrap("문자열", "result") is None


def test_fetch_novel_bundle_maps_novel_and_episodes():
    client = FakeClient(_detail(viewCount=100, chapterCount=2), [_chapter_page(2)])

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)

    assert bundle is not None
    novel, episodes = bundle
    assert novel.novel_id == "1"
    assert novel.title == "제목"
    assert [e.episode_id for e in episodes] == ["1", "2"]
    assert {e.access_type for e in episodes} == {"FREE"}


def test_fetch_novel_bundle_returns_empty_episodes_for_chapterless_novel():
    client = FakeClient(_detail(chapterCount=0), [{"result": {"list": []}}])

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)

    assert bundle is not None
    _, episodes = bundle
    assert episodes == []


def test_fetch_novel_bundle_paginates_until_short_page():
    size = CrawlConfig().chapters_page_size
    client = FakeClient(
        _detail(),
        [_chapter_page(size), _chapter_page(3, start=size + 1)],
    )

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)

    assert bundle is not None
    _, episodes = bundle
    assert len(episodes) == size + 3
    assert sum(1 for call in client.calls if "/chapters" in call) == 2


def test_fetch_novel_bundle_skips_when_detail_schema_changed():
    # result -> data 로 스키마가 바뀐 상황. 빈 행을 쓰는 대신 skip(None)이어야 한다.
    client = FakeClient({"data": {"novelInfo": {"title": "제목"}}})

    assert fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID) is None


def test_fetch_novel_bundle_skips_when_chapters_schema_changed():
    client = FakeClient(_detail(), [{"result": {"items": [{"id": 1}]}}])

    # result.list 부재는 "회차 없음"으로 간주(빈 배열)되어 정상 종료한다.
    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)
    assert bundle is not None
    assert bundle[1] == []

    # 반면 result 자체가 사라지면 스키마 변경으로 보고 skip한다.
    client = FakeClient(_detail(), [{"data": {"list": [{"id": 1}]}}])
    assert fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID) is None


def test_fetch_novel_bundle_skips_when_chapter_item_is_not_dict():
    client = FakeClient(_detail(), [{"result": {"list": ["회차1", "회차2"]}}])

    assert fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID) is None


@pytest.mark.parametrize("error", [BlockedByServerError("429"), ForbiddenPathError("robots")])
def test_fetch_novel_bundle_reraises_global_failures(error):
    # 작품 하나의 문제가 아니므로 skip이 아니라 위로 전파돼야 한다.
    client = FakeClient(_detail(), [error])

    with pytest.raises(type(error)):
        fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)


def test_describe_summarizes_response_without_dumping_body():
    assert _describe({"data": {}, "status": "ok"}) == "최상위 키=['data', 'status']"
    assert _describe(["a"]) == "타입=list"


def _mixed_page(free_count: int, paid_count: int, start: int = 1) -> dict:
    """앞쪽 free_count개는 무료, 뒤 paid_count개는 유료인 회차 페이지."""
    items = []
    for i in range(free_count + paid_count):
        num = start + i
        items.append(
            {"id": num, "title": f"{num}화", "num": num, "free": i < free_count}
        )
    return {"result": {"list": items}}


def test_free_chapters_only_stops_at_first_paid_chapter():
    size = CrawlConfig().chapters_page_size
    # 앞 25화 무료 + 나머지 유료로 100화를 채우고, 뒤에 페이지가 더 있는 상황
    client = FakeClient(_detail(), [_mixed_page(25, size - 25), _chapter_page(size, start=size + 1)])

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID, free_chapters_only=True)

    assert bundle is not None
    _, episodes = bundle
    assert len(episodes) == 25
    assert {e.access_type for e in episodes} == {"FREE"}
    # 유료를 만난 페이지에서 멈추므로 회차 페이지 요청은 1회뿐
    assert sum(1 for call in client.calls if "/chapters" in call) == 1


def test_free_chapters_only_false_collects_every_chapter():
    size = CrawlConfig().chapters_page_size
    client = FakeClient(_detail(), [_mixed_page(25, size - 25), _chapter_page(3, start=size + 1)])

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID)

    assert bundle is not None
    _, episodes = bundle
    assert len(episodes) == size + 3
    assert sum(1 for call in client.calls if "/chapters" in call) == 2


def test_free_chapters_only_drops_trailing_free_afterword():
    # 완결 후기가 마지막 회차에 무료로 붙은 케이스(실제 샘플에서 관측).
    # 선행 연속 무료 구간만 남아야 피처 계산과 일치한다.
    page = _mixed_page(25, 10)
    page["result"]["list"][-1]["free"] = True  # 마지막 회차만 다시 무료

    client = FakeClient(_detail(), [page])
    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID, free_chapters_only=True)

    assert bundle is not None
    _, episodes = bundle
    assert len(episodes) == 25
    assert [e.episode_id for e in episodes] == [str(i) for i in range(1, 26)]


def test_free_chapters_only_yields_no_episodes_when_first_chapter_is_paid():
    client = FakeClient(_detail(), [_mixed_page(0, 5)])

    bundle = fetch_novel_bundle(client, "1", CRAWLED_AT, RUN_ID, free_chapters_only=True)

    assert bundle is not None
    assert bundle[1] == []
