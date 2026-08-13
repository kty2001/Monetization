from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from clawler.http_client import BlockedByServerError, ForbiddenPathError, MunpiaHttpClient
from entity.episode import Episode
from entity.novel import Novel

logger = logging.getLogger(__name__)


class UnexpectedResponseError(Exception):
    """API 응답이 예상한 구조가 아닐 때 발생. 스키마 변경을 조용히 넘기지 않기 위함."""


def _unwrap(data: Any, *keys: str) -> Any:
    """중첩 dict에서 keys 경로를 따라 값을 꺼낸다. 경로가 없으면 None.

    키를 못 찾았을 때 원본을 그대로 돌려주면(예전 동작) API 스키마가 바뀌어도
    크롤이 그대로 진행되며 필드가 전부 빈 행만 쌓인다. 반드시 None으로 구분한다.
    """
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
        if data is None:
            return None
    return data


def _describe(data: Any) -> str:
    """예외 메시지용 응답 요약(본문 전체를 로그에 쏟지 않기 위해 최상위 키만)."""
    if isinstance(data, dict):
        return f"최상위 키={sorted(data)[:10]}"
    return f"타입={type(data).__name__}"


def fetch_novel_bundle(
    client: MunpiaHttpClient,
    novel_id: str,
    crawled_at: datetime,
    run_id: str,
    free_chapters_only: bool = False,
) -> tuple[Novel, list[Episode]] | None:
    """작품 상세 + 회차 목록을 가져와 (Novel, [Episode])로 반환한다. 실패 시 None.

    free_chapters_only: 첫 유료 회차를 만나면 그 회차부터 수집을 중단한다. 유료 섹션은
        작품당 평균 281화지만 피처로 쓰는 건 앞쪽 무료 티저(약 25화)뿐이라, 회차 페이지
        요청이 3~5회에서 1회로 줄어 크롤 시간이 크게 준다. 회차를 잘라도 Novel의
        chapter_count는 novel-detail 응답에서 오므로 총 회차 수는 그대로 보존된다.

        완결 후기가 마지막 회차에 무료로 붙는 경우가 있어(샘플 20건 중 1건) 이 옵션은
        "선행 연속 무료 구간"만 남긴다 — 피처 계산이 기대하는 것과 정확히 일치한다.
    """
    try:
        detail_path = client.config.novel_detail_path_template.format(novel_id=novel_id)
        detail_data = client.get_json(detail_path)
        novel_info = _unwrap(detail_data, "result", "novelInfo")
        if not isinstance(novel_info, dict):
            raise UnexpectedResponseError(
                f"novel-detail 응답에 result.novelInfo(dict)가 없습니다: {_describe(detail_data)}"
            )
        novel = Novel.from_api_response(
            novel_info, novel_id=novel_id, crawled_at=crawled_at, run_id=run_id
        )

        episodes: list[Episode] = []
        page = 1
        reached_paid = False
        while not reached_paid:
            chapters_path = client.config.chapters_path_template.format(
                novel_id=novel_id, page=page, size=client.config.chapters_page_size
            )
            chapters_data = client.get_json(chapters_path)
            result = _unwrap(chapters_data, "result")
            if not isinstance(result, dict):
                raise UnexpectedResponseError(
                    f"chapters 응답에 result(dict)가 없습니다: {_describe(chapters_data)}"
                )
            # 회차가 하나도 없는 작품은 result.list가 빈 배열로 온다(정상).
            items = result.get("list") or []
            if not isinstance(items, list):
                raise UnexpectedResponseError(
                    f"chapters 응답의 result.list가 배열이 아닙니다: {type(items).__name__}"
                )
            if not items:
                break
            for item in items:
                if not isinstance(item, dict):
                    raise UnexpectedResponseError(
                        f"chapters 응답의 회차 항목이 dict가 아닙니다: {type(item).__name__}"
                    )
                episode = Episode.from_api_response(
                    item, novel_id=novel_id, crawled_at=crawled_at, run_id=run_id
                )
                if free_chapters_only and episode.access_type == "PAID":
                    reached_paid = True
                    break
                episodes.append(episode)
            if reached_paid or len(items) < client.config.chapters_page_size:
                break
            page += 1

        return novel, episodes
    except (BlockedByServerError, ForbiddenPathError):
        # 차단/robots.txt 위반은 작품 하나의 문제가 아니므로 건너뛰지 않고 위로 올린다.
        raise
    except Exception:
        logger.warning("Skipping novel_id=%s due to error", novel_id, exc_info=True)
        return None
