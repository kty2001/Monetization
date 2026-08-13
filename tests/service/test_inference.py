"""데스크톱 앱 로직 테스트. 네트워크 호출 없이 가짜 클라이언트를 주입한다."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingRegressor

from clawler.http_client import BlockedByServerError
from service.inference import (
    Bundle,
    estimate_revenue,
    extract_novel_id,
    predict_live,
    search_catalog,
)
from service.model_training import build_pipeline, split_xy, support_bounds
from service.schema import CATEGORICAL_FEATURE_COLUMNS, NUMERIC_FEATURE_COLUMNS
from service.target_builder import TARGET_COLUMN
from tests.test_detail_crawler import FakeClient, _detail

_GENRES = ["판타지,퓨전", "현대판타지", "무협", "판타지"]


def _training_frame(rows: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    views = rng.integers(100, 500_000, rows)
    return pd.DataFrame({
        CATEGORICAL_FEATURE_COLUMNS[0]: [_GENRES[i % len(_GENRES)] for i in range(rows)],
        NUMERIC_FEATURE_COLUMNS[0]: views,
        NUMERIC_FEATURE_COLUMNS[1]: rng.random(rows),
        NUMERIC_FEATURE_COLUMNS[2]: rng.random(rows),
        NUMERIC_FEATURE_COLUMNS[3]: rng.integers(0, 5_000, rows),
        NUMERIC_FEATURE_COLUMNS[4]: rng.integers(0, 500, rows),
        TARGET_COLUMN: (views * rng.uniform(0.5, 2.0, rows)).astype(int) + 1,
    })


@pytest.fixture(scope="module")
def bundle() -> Bundle:
    df = _training_frame()
    X, y = split_xy(df)
    model = build_pipeline(HistGradientBoostingRegressor(max_iter=20, random_state=0))
    model.fit(X, y)

    catalog = pd.DataFrame({
        "novel_id": ["100", "200", "300"],
        "title": ["바람의 영주", "조선의 꿈", "인생 대격변"],
        "author": ["바톤", "순동이", "흥망성쇠"],
        "genres": ["판타지", "대체역사", "현대판타지"],
        "predicted_paid_events_per_episode": [555, 819, 1974],
        "free_views_1_10": [90000, 146795, 351363],
        "support_band": ["정상", "정상", "정상"],
    })
    return Bundle(
        catalog=catalog,
        model=model,
        support_bounds=support_bounds(X[NUMERIC_FEATURE_COLUMNS[0]]),
        meta={"snapshot_date": "20260813"},
    )


def _chapters(count: int, views: int = 5_000) -> dict:
    """무료 회차 count개짜리 chapters 응답."""
    return {
        "result": {
            "list": [
                {
                    "id": 1000 + i,
                    "title": f"{i + 1}화",
                    "num": i + 1,
                    "free": True,
                    "viewCount": max(views - i * 100, 1),
                    "likeCount": 10,
                    "commentCount": 2,
                }
                for i in range(count)
            ]
        }
    }


# ── URL / 작품 번호 파싱 ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text, expected",
    [
        ("123456", "123456"),
        ("https://novel.munpia.com/123456", "123456"),
        ("https://www.munpia.com/novel/123456?page=2", "123456"),
        ("  584035  ", "584035"),
        # 짧은 숫자가 섞여 있어도 가장 긴 것을 고른다.
        ("https://example.com/v2/novel/584035", "584035"),
    ],
)
def test_extract_novel_id_handles_urls_and_bare_numbers(text, expected):
    assert extract_novel_id(text) == expected


@pytest.mark.parametrize("text", ["", "제목만 입력함", "12", None])
def test_extract_novel_id_returns_none_when_absent(text):
    assert extract_novel_id(text) is None


# ── 카탈로그 검색 ────────────────────────────────────────────────────────────


def test_search_catalog_matches_title_and_author(bundle):
    assert list(search_catalog(bundle.catalog, "조선")["novel_id"]) == ["200"]
    assert list(search_catalog(bundle.catalog, "바톤")["novel_id"]) == ["100"]


def test_search_catalog_ignores_spacing_and_case(bundle):
    assert list(search_catalog(bundle.catalog, "바람의영주")["novel_id"]) == ["100"]


def test_search_catalog_returns_empty_for_no_match_or_blank(bundle):
    assert search_catalog(bundle.catalog, "없는작품").empty
    assert search_catalog(bundle.catalog, "   ").empty


# ── 실시간 예측 ──────────────────────────────────────────────────────────────


def test_predict_live_returns_prediction_for_sufficient_episodes(bundle):
    client = FakeClient(_detail(genres=["판타지"], chapterCount=30), [_chapters(30)])

    result = predict_live(client, "123456", bundle)

    assert result.ok
    assert result.title == "제목"
    assert result.predicted_paid_events_per_episode > 0
    assert result.support_band in {"정상", "희박(하한 미만)", "희박(상한 초과)"}
    assert result.leading_free_episodes == 30


def test_predict_live_explains_when_episodes_are_too_few(bundle):
    client = FakeClient(_detail(genres=["판타지"], chapterCount=4), [_chapters(4)])

    result = predict_live(client, "123456", bundle)

    assert not result.ok
    assert result.predicted_paid_events_per_episode is None
    assert result.leading_free_episodes == 4
    assert "10화" in result.reason


def test_predict_live_handles_novel_with_no_episodes(bundle):
    client = FakeClient(_detail(genres=["판타지"]), [{"result": {"list": []}}])

    result = predict_live(client, "123456", bundle)

    assert not result.ok
    assert result.leading_free_episodes == 0


def test_predict_live_reports_missing_novel(bundle):
    """fetch_novel_bundle은 실패 시 None을 반환한다 — 앱은 이를 사유로 바꿔야 한다."""
    client = FakeClient({"result": {}}, [_chapters(30)])

    result = predict_live(client, "999999", bundle)

    assert not result.ok
    assert "999999" in result.reason


def test_predict_live_covers_network_failure_in_the_same_reason(bundle):
    """네트워크 오류도 fetch_novel_bundle 안에서 None이 되므로 원인을 구분할 수 없다.

    안내 문구가 '작품이 없다'로만 단정하지 않고 연결 확인까지 언급해야 한다.
    """

    class BrokenClient(FakeClient):
        def get_json(self, path, params=None):
            raise ConnectionError("boom")

    result = predict_live(BrokenClient(_detail()), "123456", bundle)

    assert not result.ok
    assert "인터넷" in result.reason


def test_predict_live_surfaces_server_block_distinctly(bundle):
    """차단(403/429)만은 예외로 올라오므로 별도 안내가 가능하다."""

    class BlockedClient(FakeClient):
        def get_json(self, path, params=None):
            raise BlockedByServerError("429")

    result = predict_live(BlockedClient(_detail()), "123456", bundle)

    assert not result.ok
    assert "차단" in result.reason


# ── 매출 환산 ────────────────────────────────────────────────────────────────


def test_estimate_revenue_is_plain_multiplication():
    assert estimate_revenue(1_000, 100) == 100_000
    assert estimate_revenue(0, 100) == 0
