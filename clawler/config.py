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
    # TODO: 실제 페이지 파라미터를 라이브 HTML에서 확인 후 필요시 수정
    list_path_template: str = "/?menu=novel&action=list&section=nv.free&page={page}"

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
        }
    )

    request_delay_seconds: float = float(os.environ.get("MUNPIA_REQUEST_DELAY_SECONDS", "1.2"))
    max_retries: int = int(os.environ.get("MUNPIA_MAX_RETRIES", "3"))
    request_timeout_seconds: float = float(os.environ.get("MUNPIA_TIMEOUT_SECONDS", "10"))
    forbidden_path_prefixes: tuple[str, ...] = FORBIDDEN_PATH_PREFIXES

    @classmethod
    def from_env(cls) -> "CrawlConfig":
        return cls()
