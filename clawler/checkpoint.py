from __future__ import annotations

from pathlib import Path

_CHECKPOINT_PREFIX = ".processed_novel_ids_"
_CHECKPOINT_SUFFIX = ".log"


class CrawlCheckpoint:
    """처리 완료된 novel_id를 append-only 로그 파일로 기록해 크롤 재개를 지원한다.

    목록 페이지 자체는 재개 시 항상 1페이지부터 다시 스캔한다(요청 자체는 저비용이라
    페이지 진행 상태까지 별도로 관리하지 않아도 됨). 이미 처리된 novel_id는 이
    체크포인트로 건너뛰므로 중복 수집/중복 CSV row는 발생하지 않는다.
    """

    def __init__(self, run_id: str, base_dir: Path) -> None:
        self.run_id = run_id
        self.base_dir = base_dir
        self.path = base_dir / f"{_CHECKPOINT_PREFIX}{run_id}{_CHECKPOINT_SUFFIX}"
        self.processed_novel_ids: set[str] = set()
        if self.path.exists():
            self.processed_novel_ids = {
                line.strip()
                for line in self.path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }

    @classmethod
    def find_latest(cls, base_dir: Path) -> "CrawlCheckpoint | None":
        if not base_dir.exists():
            return None
        candidates = sorted(
            base_dir.glob(f"{_CHECKPOINT_PREFIX}*{_CHECKPOINT_SUFFIX}"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None
        run_id = candidates[0].name[len(_CHECKPOINT_PREFIX) : -len(_CHECKPOINT_SUFFIX)]
        return cls(run_id=run_id, base_dir=base_dir)

    def is_done(self, novel_id: str) -> bool:
        return novel_id in self.processed_novel_ids

    def mark_done(self, novel_id: str) -> None:
        self.processed_novel_ids.add(novel_id)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"{novel_id}\n")
