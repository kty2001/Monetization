import json
from pathlib import Path

from clawler.config import CrawlConfig
from clawler.list_crawler import iter_list_page_items, parse_list_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_list_page_extracts_unique_novel_ids_and_total_pages():
    data = json.loads((FIXTURES / "list_page_sample.json").read_text(encoding="utf-8"))

    novel_ids, total_pages = parse_list_page(data)

    assert novel_ids == ["592090", "589442"]
    assert total_pages == 42


def test_parse_list_page_defaults_total_pages_to_one_when_missing():
    data = {"list": [{"nvSrl": 1}]}

    novel_ids, total_pages = parse_list_page(data)

    assert novel_ids == ["1"]
    assert total_pages == 1


def test_parse_list_page_handles_empty_list():
    novel_ids, total_pages = parse_list_page({"list": []})

    assert novel_ids == []
    assert total_pages == 1


class _FakeClient:
    """요청된 page 번호를 기록하고 고정된 목록 응답을 돌려주는 가짜 클라이언트."""

    def __init__(self, total_pages: int):
        self.config = CrawlConfig()
        self.total_pages = total_pages
        self.requested_pages: list[int] = []

    def get_list_json(self, path: str) -> dict:
        page = int(path.rsplit("page=", 1)[1])
        self.requested_pages.append(page)
        return {"list": [{"nvSrl": page * 10}], "last": self.total_pages}


def test_iter_list_page_items_starts_at_page_one_by_default():
    client = _FakeClient(total_pages=3)

    pages = list(iter_list_page_items(client))

    assert client.requested_pages == [1, 2, 3]
    assert [item["nvSrl"] for page in pages for item in page] == [10, 20, 30]


def test_iter_list_page_items_skips_ahead_with_start_page():
    # 재개 시 앞 페이지 재스캔을 건너뛴다.
    client = _FakeClient(total_pages=5)

    list(iter_list_page_items(client, start_page=4))

    assert client.requested_pages == [4, 5]


def test_iter_list_page_items_max_pages_is_an_absolute_page_number():
    client = _FakeClient(total_pages=10)

    list(iter_list_page_items(client, max_pages=6, start_page=4))

    assert client.requested_pages == [4, 5, 6]
