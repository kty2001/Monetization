from __future__ import annotations

import re

from bs4 import BeautifulSoup

from clawler.http_client import MunpiaHttpClient

# 실제 목록 페이지(mm.munpia.com) 구조 확인 결과:
# - 각 작품 <li onclick="view_novel(592090, 'nv.free');" ...> 에서 첫 번째 인자가 novel_id
# - 전체 페이지 수는 <span id="list_last">2441</span> 에 노출됨
_NOVEL_ID_PATTERN = re.compile(r"view_novel\(\s*(\d+)\s*,")


def parse_list_page(html: str) -> tuple[list[str], int]:
    soup = BeautifulSoup(html, "html.parser")

    novel_ids: list[str] = []
    seen: set[str] = set()
    for match in _NOVEL_ID_PATTERN.finditer(html):
        novel_id = match.group(1)
        if novel_id not in seen:
            seen.add(novel_id)
            novel_ids.append(novel_id)

    total_pages = 1
    last_page_el = soup.select_one("#list_last")
    if last_page_el and last_page_el.get_text(strip=True).isdigit():
        total_pages = int(last_page_el.get_text(strip=True))

    return novel_ids, total_pages


def fetch_novel_ids(client: MunpiaHttpClient, max_pages: int | None = None) -> list[str]:
    all_ids: list[str] = []
    seen: set[str] = set()

    page = 1
    total_pages = 1
    while page <= total_pages:
        if max_pages is not None and page > max_pages:
            break
        path = client.config.list_path_template.format(page=page)
        html = client.get_html(path)
        ids, total_pages = parse_list_page(html)
        for novel_id in ids:
            if novel_id not in seen:
                seen.add(novel_id)
                all_ids.append(novel_id)
        page += 1

    return all_ids
