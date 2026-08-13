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


def iter_list_pages(
    client: MunpiaHttpClient, max_pages: int | None = None, start_page: int = 1
) -> Iterator[list[str]]:
    """목록 페이지를 순회하며 페이지별 novel_id 목록을 yield한다."""
    for items in iter_list_page_items(client, max_pages=max_pages, start_page=start_page):
        yield [str(item["nvSrl"]) for item in items]


def iter_list_page_items(
    client: MunpiaHttpClient, max_pages: int | None = None, start_page: int = 1
) -> Iterator[list[dict]]:
    """목록 페이지를 순회하며 페이지별 원본 item dict 목록을 yield한다.

    start_page: 시작 페이지(기본 1). 재개 시 이미 처리한 구간을 다시 훑지 않기 위한
        옵션 — 체크포인트만으로 재개하면 앞 페이지를 전부 재스캔하느라 페이지당
        딜레이가 그대로 든다(48,000건 규모에서 20분 이상). 단, 목록 정렬이 크롤
        도중에도 바뀌므로 건너뛴 구간으로 밀려온 작품은 놓칠 수 있다.
    max_pages: 마지막 페이지 번호(시작 페이지 기준 개수가 아니라 절대 번호).
    """
    page = start_page
    total_pages = start_page
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
