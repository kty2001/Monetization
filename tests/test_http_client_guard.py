import pytest

from clawler.config import CrawlConfig
from clawler.http_client import ForbiddenPathError, MunpiaHttpClient


@pytest.fixture
def client():
    return MunpiaHttpClient(CrawlConfig())


@pytest.mark.parametrize(
    "path",
    ["/novel/viewer/123", "/novel/viewer/123?page=1", "/app_api/some-endpoint"],
)
def test_guard_path_blocks_disallowed_prefixes(client, path):
    with pytest.raises(ForbiddenPathError):
        client._guard_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/novel/detail/123",
        "/api/v1/pc/novel-detail/123",
        "/?ajx=1&menu=novel&action=list&section=nv.free&keyword=&page=1",
    ],
)
def test_guard_path_allows_expected_prefixes(client, path):
    client._guard_path(path)
