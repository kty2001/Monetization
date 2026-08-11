import json
from pathlib import Path

from clawler.list_crawler import parse_list_page

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
