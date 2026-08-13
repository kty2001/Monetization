"""NovelStats → 학습 타겟.

타겟은 **회차당 구매 건수**다 — 목록 API의 `nvSumPurchased`를 유료 회차 수로 나눈 값.

`nvSumPurchased`는 회차당 수치가 아니라 **작품 전체 누적 구매 건수**다(2026-08-13 확인:
총 구매수 중앙값 64,764 / 유료 회차수 중앙값 175 → 회차당 397건. 유료 회차 수와의
스피어만 상관 0.405). 이걸 그대로 타겟으로 쓰면 두 가지 문제가 생긴다.

1. **해석 오류**: 앱이 "회차당 구매수"로 표시해 단가를 곱하면 회차당 매출이 100배 넘게
   부풀려진다(실제로 회차당 1,100만원 같은 값이 나왔다).
2. **예측 성능 손해**: 총 구매수는 "회차당 인기"와 "몇 화까지 연재했는가"가 섞인 값인데,
   후자는 앞 10화로 알 수 없어 타겟의 순수 잡음이 된다. 회차당으로 나누면 logRMSE가
   0.9036 → 0.6947, MdAPE가 51.3% → 40.6%로 크게 좋아진다.

매출 환산은 여기서 하지 않는다 — 회차 단가가 작가별 계약에 따라 달라 크롤로 확보할 수
없으므로, 앱에서 사용자가 입력한 단가를 곱한다(`회차당 예상 매출 = 회차당 구매수 × 단가`).
"""

from __future__ import annotations

from typing import NamedTuple

import pandas as pd

TARGET_COLUMN = "target_paid_events_per_episode"


class TargetResult(NamedTuple):
    frame: pd.DataFrame
    dropped_count: int


def paid_episode_counts(novels_df: pd.DataFrame, episodes_df: pd.DataFrame) -> pd.Series:
    """작품별 **유료 회차 수**를 센다.

    유료 회차는 수집하지 않으므로(`--free-chapters-only`) 직접 셀 수 없다. 대신
    `chapter_count`(novel-detail 응답의 총 회차 수, 회차 수집을 잘라도 보존된다)에서
    수집한 선행 무료 회차 수를 뺀다.
    """
    collected_free = episodes_df.groupby("novel_id").size()
    total = pd.to_numeric(novels_df.set_index("novel_id")["chapter_count"], errors="coerce")
    paid = total - collected_free.reindex(total.index).fillna(0)
    # 0 이하가 나오면(총 회차 수가 결측이거나 어긋난 경우) 나눗셈이 깨지므로 최소 1로 둔다.
    return paid.clip(lower=1).rename("paid_episodes")


def build_target(stats_df: pd.DataFrame, paid_episodes: pd.Series) -> TargetResult:
    """`novel_id`, `target_paid_events_per_episode` 두 컬럼과 제외된 작품 수를 반환한다.

    구매수가 0/결측이거나 유료 회차 수를 알 수 없는 작품은 학습셋에서 제외한다.
    유료로 전환됐는데 구매가 0인 작품은 타겟이 사실상 관측되지 않은 것에 가깝고,
    log1p 학습에서도 정보를 주지 못한다.
    """
    purchased = pd.to_numeric(stats_df["purchased_count"], errors="coerce")
    episodes = pd.to_numeric(
        stats_df["novel_id"].map(paid_episodes), errors="coerce"
    )

    keep = purchased.notna() & (purchased > 0) & episodes.notna() & (episodes > 0)

    frame = pd.DataFrame(
        {
            "novel_id": stats_df.loc[keep, "novel_id"],
            TARGET_COLUMN: (purchased[keep] / episodes[keep]).astype("float64"),
        }
    ).reset_index(drop=True)

    return TargetResult(frame=frame, dropped_count=int((~keep).sum()))
