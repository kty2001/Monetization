"""데스크톱 앱이 쓰는 조회·예측 로직 (UI 없음).

앱(`app/main.py`)은 이 모듈만 호출한다. Tkinter 코드에 로직이 섞이면 테스트할 수 없으므로
크롤·피처·예측 경로를 전부 여기에 모은다. 실제 크롤·피처 계산은 기존 모듈을 그대로 쓴다.

두 가지 경로를 제공한다:

- **조회**: 번들에 실린 스냅샷(`catalog.csv`)에서 제목·작가로 찾는다. 네트워크 불필요.
- **실시간 분석**: 작품 번호로 문피아를 직접 크롤해 예측한다. 스냅샷에 없는 작품
  (연재 중인 신작 등)을 위한 경로 — 스냅샷의 89%가 30일 이상 갱신이 없는 방치작이라
  정작 유료 전환을 고민하는 작가는 조회만으로는 자기 작품을 찾지 못한다.
"""

from __future__ import annotations

import json
import pickle
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple
from zoneinfo import ZoneInfo

import pandas as pd

from clawler.detail_crawler import fetch_novel_bundle
from clawler.http_client import BlockedByServerError, ForbiddenPathError
from service.episode_features import DEFAULT_N, compute_episode_features, leading_free_episodes
from service.model_training import support_band
from service.novel_features import build_novel_features
from service.schema import CATEGORICAL_FEATURE_COLUMNS, ID_COLUMN, NUMERIC_FEATURE_COLUMNS

_KST = ZoneInfo("Asia/Seoul")

#: 붙여넣은 URL/번호에서 작품 번호를 뽑는 패턴.
#: 문피아 공개 작품 페이지의 URL 형식이 저장소에 기록돼 있지 않아(문서에는 API 경로만 있다)
#: 특정 형식을 하드코딩하지 않는다. 4자리 이상 연속 숫자를 후보로 삼고, 실제로 맞는지는
#: detail API 호출 결과로 판정한다.
_NOVEL_ID_PATTERN = re.compile(r"\d{4,}")

CATALOG_COLUMNS = [
    ID_COLUMN,
    "title",
    "author",
    "genres",
    "predicted_paid_events_per_episode",
    "free_views_1_10",
    "support_band",
]


class Bundle(NamedTuple):
    """앱과 함께 배포되는 데이터 묶음."""

    catalog: pd.DataFrame
    model: Any
    support_bounds: Any
    meta: dict[str, Any]


@dataclass
class PredictionResult:
    """실시간 분석 결과. 실패해도 예외 대신 이 객체로 사유를 돌려준다.

    UI가 예외를 잡아 문자열로 바꾸는 대신, 실패를 값으로 다루게 해서 테스트를 쉽게 한다.
    """

    ok: bool
    novel_id: str
    title: str | None = None
    author: str | None = None
    predicted_paid_events_per_episode: int | None = None
    support_band: str | None = None
    leading_free_episodes: int | None = None
    reason: str | None = None


def load_bundle(bundle_dir: Path) -> Bundle:
    """`scripts/build_app_bundle.py`가 만든 번들을 읽는다."""
    catalog_path = bundle_dir / "catalog.csv"
    model_path = bundle_dir / "model.pkl"
    meta_path = bundle_dir / "meta.json"

    missing = [p.name for p in (catalog_path, model_path, meta_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"'{bundle_dir}'에 {', '.join(missing)}이(가) 없습니다. "
            "scripts/build_app_bundle.py를 먼저 실행하세요."
        )

    with model_path.open("rb") as handle:
        artifact = pickle.load(handle)

    return Bundle(
        catalog=pd.read_csv(catalog_path, dtype={ID_COLUMN: str}),
        model=artifact["model"],
        support_bounds=artifact["support_bounds"],
        meta=json.loads(meta_path.read_text(encoding="utf-8")),
    )


def search_catalog(catalog: pd.DataFrame, query: str, limit: int = 50) -> pd.DataFrame:
    """제목 또는 작가명 부분일치로 찾는다(대소문자·공백 무시).

    작가는 자기 작품 제목을 정확히 알지만 띄어쓰기가 다를 수 있으므로 공백을 지우고 비교한다.
    """
    normalized = query.strip().replace(" ", "").lower()
    if not normalized:
        return catalog.head(0)

    def _norm(series: pd.Series) -> pd.Series:
        return series.fillna("").str.replace(" ", "", regex=False).str.lower()

    hit = _norm(catalog["title"]).str.contains(normalized, regex=False) | _norm(
        catalog["author"]
    ).str.contains(normalized, regex=False)
    return catalog[hit].head(limit)


def extract_novel_id(text: str) -> str | None:
    """붙여넣은 URL이나 작품 번호에서 작품 번호를 뽑는다.

    URL 형식을 가정하지 않고 4자리 이상 숫자 중 **가장 긴 것**을 고른다 — URL에 페이지
    번호처럼 짧은 숫자가 섞여 있어도 작품 번호가 더 길다.
    """
    candidates = _NOVEL_ID_PATTERN.findall(text or "")
    if not candidates:
        return None
    return max(candidates, key=len)


def predict_live(client: Any, novel_id: str, bundle: Bundle) -> PredictionResult:
    """작품을 직접 크롤해 예측한다. 실패 사유는 예외가 아니라 결과 객체로 돌려준다."""
    try:
        crawled = fetch_novel_bundle(
            client,
            novel_id,
            datetime.now(_KST),
            run_id="live",
            free_chapters_only=True,
        )
    except (BlockedByServerError, ForbiddenPathError):
        return PredictionResult(
            ok=False,
            novel_id=novel_id,
            reason="문피아 접속이 일시적으로 차단됐습니다. 잠시 후 다시 시도해 주세요.",
        )

    if crawled is None:
        # fetch_novel_bundle은 대량 크롤에서 문제 작품을 건너뛰려고 네트워크 오류까지
        # 삼켜 None을 돌려준다(차단만 예외로 올라온다). 둘을 구분할 수 없으므로 두 가지
        # 원인을 모두 안내한다 — "작품이 없다"고만 하면 인터넷이 끊겼을 때 오해를 준다.
        return PredictionResult(
            ok=False,
            novel_id=novel_id,
            reason=(
                f"작품 번호 {novel_id}의 정보를 가져오지 못했습니다. "
                "번호가 맞는지, 인터넷이 연결돼 있는지 확인해 주세요."
            ),
        )

    novel, episodes = crawled
    episodes_df = pd.DataFrame([episode.to_row() for episode in episodes])
    features = (
        compute_episode_features(episodes_df, n=DEFAULT_N)
        if not episodes_df.empty
        else pd.DataFrame()
    )

    if features.empty:
        available = 0 if episodes_df.empty else len(leading_free_episodes(episodes_df))
        return PredictionResult(
            ok=False,
            novel_id=novel_id,
            title=novel.title,
            author=novel.author,
            leading_free_episodes=available,
            reason=(
                f"앞 {DEFAULT_N}화를 기준으로 예측하므로 무료 회차가 최소 {DEFAULT_N}화 "
                f"필요합니다 (현재 {available}화)."
            ),
        )

    frame = build_novel_features(pd.DataFrame([novel.to_row()]), features)
    X = frame[CATEGORICAL_FEATURE_COLUMNS + NUMERIC_FEATURE_COLUMNS]
    predicted = float(bundle.model.predict(X)[0])
    band = support_band(frame[NUMERIC_FEATURE_COLUMNS[0]], bundle.support_bounds).iloc[0]

    return PredictionResult(
        ok=True,
        novel_id=novel_id,
        title=novel.title,
        author=novel.author,
        predicted_paid_events_per_episode=int(round(predicted)),
        support_band=str(band),
        leading_free_episodes=int(frame["leading_free_episodes"].iloc[0]),
    )


def estimate_revenue(paid_events_per_episode: int, unit_price: int) -> int:
    """**회차당** 예상 매출 = 회차당 예측 구매수 × 회차 단가.

    작품 전체 매출이 아니라 회차 1편 기준이다 — 전체가 필요하면 유료 연재 회차 수를
    곱한다. 예전에는 타겟이 작품 전체 누적 구매수인데 화면에는 "회차당"으로 표시해
    회차당 매출이 100배 넘게 부풀려졌다(`service/target_builder.py` 참고).

    단가는 작가별 계약에 따라 달라 크롤할 수 없으므로 모델에 일절 개입하지 않는다.
    여기서는 단순 곱셈만 한다(상수배라 작품 간 순위도 바뀌지 않는다).
    """
    return int(paid_events_per_episode) * int(unit_price)
