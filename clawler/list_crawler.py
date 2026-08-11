from __future__ import annotations

from collections.abc import Iterator

from clawler.http_client import MunpiaHttpClient


def parse_list_page_items(data: dict) -> tuple[list[dict], int]:
    """ajx=1 AJAX 응답(JSON)에서 원본 item dict 목록(nvSumPurchased 등 포함)과
    전체 페이지 수를 추출한다. nvSrl 기준으로 중복 제거."""
    raw_items = data.get("list") or []
    items: list[dict] = []
    seen: set[str] = set()
    for item in raw_items:
        novel_id = item.get("nvSrl")
        if novel_id is None:
            continue
        novel_id = str(novel_id)
        if novel_id not in seen:
            seen.add(novel_id)
            items.append(item)
    total_pages = data.get("last") or 1
    return items, total_pages


def parse_list_page(data: dict) -> tuple[list[str], int]:
    """ajx=1 AJAX 응답(JSON)에서 novel_id 목록과 전체 페이지 수를 추출한다."""
    items, total_pages = parse_list_page_items(data)
    novel_ids = [str(item["nvSrl"]) for item in items]
    return novel_ids, total_pages


def iter_list_pages(client: MunpiaHttpClient, max_pages: int | None = None) -> Iterator[list[str]]:
    """목록 페이지를 1페이지부터 순회하며 페이지별 novel_id 목록을 yield한다."""
    for items in iter_list_page_items(client, max_pages=max_pages):
        yield [str(item["nvSrl"]) for item in items]


def iter_list_page_items(
    client: MunpiaHttpClient, max_pages: int | None = None
) -> Iterator[list[dict]]:
    """목록 페이지를 1페이지부터 순회하며 페이지별 원본 item dict 목록을 yield한다."""
    page = 1
    total_pages = 1
    while page <= total_pages:
        if max_pages is not None and page > max_pages:
            break
        path = client.config.list_path_template.format(
            section=client.config.section, page=page
        )
        data = client.get_list_json(path)
        items, total_pages = parse_list_page_items(data)
        yield items
        page += 1
