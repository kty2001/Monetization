from pathlib import Path

from clawler.list_crawler import parse_list_page

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_list_page_extracts_unique_novel_ids_and_total_pages():
    html = (FIXTURES / "list_page_sample.html").read_text(encoding="utf-8")

    novel_ids, total_pages = parse_list_page(html)

    assert novel_ids == ["592090", "589442"]
    assert total_pages == 42


def test_parse_list_page_defaults_total_pages_to_one_without_pagination():
    html = '<html><body><li onclick="view_novel(1, \'nv.free\');"></li></body></html>'

    novel_ids, total_pages = parse_list_page(html)

    assert novel_ids == ["1"]
    assert total_pages == 1
