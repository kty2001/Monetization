from __future__ import annotations

import logging
import time

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from clawler.config import CrawlConfig

logger = logging.getLogger(__name__)


class ForbiddenPathError(Exception):
    """요청 경로가 robots.txt상 Disallow된 경로에 해당할 때 발생."""


class BlockedByServerError(Exception):
    """서버가 403/429로 응답해 크롤링이 차단되었을 때 발생. 재시도하지 않고 즉시 중단."""


def _is_retryable(exception: BaseException) -> bool:
    if isinstance(exception, BlockedByServerError):
        return False
    if isinstance(exception, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exception, requests.exceptions.HTTPError):
        response = exception.response
        return response is not None and 500 <= response.status_code < 600
    return False


class MunpiaHttpClient:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(config.headers)

    def _guard_path(self, path: str) -> None:
        for prefix in self.config.forbidden_path_prefixes:
            if path.startswith(prefix):
                raise ForbiddenPathError(f"Disallowed path per robots.txt: {path}")

    def _send(self, url: str, path: str, params: dict | None = None) -> requests.Response:
        self._guard_path(path)

        @retry(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(self.config.max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        def _do_request() -> requests.Response:
            response = self.session.get(
                url, params=params, timeout=self.config.request_timeout_seconds
            )
            if response.status_code in (403, 429):
                raise BlockedByServerError(
                    f"Received {response.status_code} from {url} — aborting crawl"
                )
            response.raise_for_status()
            return response

        try:
            return _do_request()
        finally:
            time.sleep(self.config.request_delay_seconds)

    def get_list_json(self, path: str) -> dict:
        url = f"{self.config.list_base_url}{path}"
        return self._send(url, path).json()

    def get_json(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.config.api_base_url}{path}"
        return self._send(url, path, params=params).json()
