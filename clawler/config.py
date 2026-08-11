from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/138.0 Safari/537.36"
)

# 참고 프로젝트에서 역공학한 비공식 엔드포인트. robots.txt 상 허용되지만
# 실제 응답 스키마/경로는 소규모 테스트 크롤로 반드시 검증할 것.
FORBIDDEN_PATH_PREFIXES: tuple[str, ...] = ("/novel/viewer/", "/app_api/")


@dataclass(frozen=True)
class CrawlConfig:
    list_base_url: str = "https://mm.munpia.com"
    # 목록 페이지는 순수 GET(page=N)으로는 항상 1페이지와 동일한 내용을 반환한다.
    # 실제 페이지네이션은 JS의 view_list()가 호출하는 ajx=1 AJAX(JSON) 엔드포인트를 통해서만 동작한다.
    # section: nv.free(무료 자유연재, 기본값) / pl.serial(선연재 유료) / pl.serial_end(완결 유료) 등
    section: str = "nv.free"
    list_path_template: str = "/?ajx=1&menu=novel&action=list&section={section}&keyword=&page={page}"

    api_base_url: str = "https://www.munpia.com"
    novel_detail_path_template: str = "/api/v1/pc/novel-detail/{novel_id}"
    chapters_path_template: str = (
        "/api/v1/pc/novel-detail/{novel_id}/chapters"
        "?order=ENTRY_FIRST&page={page}&size={size}"
    )
    chapters_page_size: int = 100

    headers: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": os.environ.get("MUNPIA_USER_AGENT", DEFAULT_USER_AGENT),
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.munpia.com",
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    request_delay_seconds: float = float(os.environ.get("MUNPIA_REQUEST_DELAY_SECONDS", "1.2"))
    max_retries: int = int(os.environ.get("MUNPIA_MAX_RETRIES", "3"))
    request_timeout_seconds: float = float(os.environ.get("MUNPIA_TIMEOUT_SECONDS", "10"))
    forbidden_path_prefixes: tuple[str, ...] = FORBIDDEN_PATH_PREFIXES

    @classmethod
    def from_env(cls) -> "CrawlConfig":
        return cls()
