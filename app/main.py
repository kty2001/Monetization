"""문피아 유료 전환 매출 예측 — 데스크톱 앱 진입점.

    uv run python -m app.main        # 개발 모드
    MunpiaRevenue.exe                # 배포본

로직은 `service/inference.py`에 있다. 이 파일은 화면과 스레드 처리만 담당한다.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from clawler.config import CrawlConfig
from clawler.http_client import MunpiaHttpClient
from service.inference import (
    Bundle,
    PredictionResult,
    estimate_revenue,
    extract_novel_id,
    load_bundle,
    predict_live,
    search_catalog,
)

APP_TITLE = "문피아 유료 전환 매출 예측"
DEFAULT_UNIT_PRICE = 100

#: 설계 기준 창 크기. 화면이 이보다 작으면 화면에 맞춰 줄인다(창이 화면 밖으로 나가면
#: 아래쪽 위젯에 손이 닿지 않는다).
DESIGN_WIDTH = 960
DESIGN_HEIGHT = 540

# 폰트는 960×540 안에 경고 문구까지 다 들어가는 선에서 최대한 키운 값이다.
# 이보다 키우면 아래쪽 support_band 경고와 면책 문구가 잘린다(실측으로 맞췄다).
_FONT = ("맑은 고딕", 10)
_FONT_BOLD = ("맑은 고딕", 11, "bold")
_FONT_BIG = ("맑은 고딕", 22, "bold")
_FONT_SMALL = ("맑은 고딕", 9)
_ROW_HEIGHT = 24
_WRAP = 900

_DISCLAIMER = (
    "이 예측값은 '유료로 전환했을 때'를 가정한 값입니다. "
    "전환 여부나 성공 확률 자체를 예측하지는 않습니다."
)
_SPARSE_WARNING = (
    "⚠ 비슷한 조회수의 유료 전환 사례가 학습 데이터에 거의 없는 구간입니다. "
    "숫자를 그대로 믿기보다 참고용으로만 보세요."
)
_PRICE_NOTE = (
    "회차당 예상 매출 = 회차당 예측 구매수 × 회차 단가 "
    "(단가는 예측에 쓰이지 않는 단순 곱셈입니다). "
    "작품 전체 매출을 보려면 여기에 유료 연재할 회차 수를 곱하세요."
)


def bundle_dir() -> Path:
    """번들 위치. PyInstaller로 묶이면 임시 추출 경로(`sys._MEIPASS`) 아래에 있다."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "bundle"


def close_splash() -> None:
    """onefile 배포본의 스플래시를 닫는다.

    `pyi_splash`는 PyInstaller가 frozen 앱 안에만 넣어주는 모듈이라 개발 모드에는 없다.
    닫는 데 실패해도 앱 자체는 정상 동작해야 하므로 예외를 삼킨다.
    """
    try:
        import pyi_splash  # type: ignore[import-not-found]

        pyi_splash.close()
    except Exception:
        pass


def scope_text(meta: dict) -> str:
    """검색 범위를 사실대로 적는다.

    이전에는 예측을 돌린 날짜를 '수집 시점'으로 표시했고(실제 크롤은 그 며칠 전이다),
    대상이 무료 자유연재뿐이라는 것도 회차 조건으로 대부분이 빠졌다는 것도 알리지 않아
    "어디서 검색하는지 모르겠다"는 피드백을 받았다. 값은 전부 meta.json에서 가져온다.
    """
    total = meta.get("source_total", 0)
    rows = meta.get("catalog_rows", 0)
    minimum = meta.get("min_free_episodes", 10)
    section = meta.get("section", "무료 연재")
    period = f"{meta.get('crawl_start', '?')}~{meta.get('crawl_end', '?')}"
    return (
        f"검색 범위 — 문피아 {section} {total:,}작품({period} 수집) 중 "
        f"무료 {minimum}화 이상인 {rows:,}작품.\n"
        f"이미 유료 연재 중인 작품과 무료 {minimum}화 미만인 작품({total - rows:,}건)은 "
        "목록에 없습니다. 아래에서 작품 주소로 직접 분석하세요."
    )


class App(ttk.Frame):
    def __init__(self, master: tk.Tk, bundle: Bundle) -> None:
        super().__init__(master, padding=8)
        self.bundle = bundle
        self.result: PredictionResult | None = None
        self._queue: queue.Queue[PredictionResult] = queue.Queue()

        self.pack(fill="both", expand=True)
        # 아래쪽부터 배치한다. 위에서부터 쌓으면 창이 낮을 때 pack이 마지막 영역을 잘라내
        # support_band 경고와 면책 문구가 화면 밖으로 밀린다 — 반드시 보여야 하는 것들이다.
        # 결과·분석 영역이 필요한 높이를 먼저 확보하고, 남는 공간을 검색 목록이 가져간다.
        self._build_result()
        self._build_live()
        self._build_search()

    # ── 화면 구성 ────────────────────────────────────────────────────────

    def _build_search(self) -> None:
        box = ttk.LabelFrame(self, text="1. 작품 찾기", padding=6)
        box.pack(side="top", fill="both", expand=True)

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="제목 또는 작가명", font=_FONT).pack(side="left")
        self.search_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.search_var, font=_FONT)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda _event: self._on_search())
        ttk.Button(row, text="검색", command=self._on_search).pack(side="left")

        self.tree = ttk.Treeview(
            box, columns=("title", "author", "predicted", "band"), show="headings", height=6
        )
        # 합이 창 너비(960)를 넘으면 신뢰도 컬럼이 오른쪽으로 밀려 안 보인다.
        for key, label, width in (
            ("title", "제목", 380),
            ("author", "작가", 130),
            ("predicted", "회차당 구매수", 140),
            ("band", "신뢰도", 170),
        ):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, anchor="w")
        # 범위 문구를 먼저 아래에 붙인다. 목록(expand=True)보다 뒤에 배치하면 공간이
        # 부족할 때 pack이 이 라벨을 밀어내 아예 사라진다(창이 작을수록 확실히 사라진다).
        self.scope_label = ttk.Label(
            box,
            text=scope_text(self.bundle.meta),
            font=_FONT_SMALL,
            foreground="#555555",
            wraplength=_WRAP,
            justify="left",
        )
        self.scope_label.pack(side="bottom", anchor="w", pady=(4, 0))

        self.tree.pack(fill="both", expand=True, pady=(4, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    def _build_live(self) -> None:
        minimum = self.bundle.meta.get("min_free_episodes", 10)
        box = ttk.LabelFrame(
            self,
            text=f"2. 목록에 없는 작품 분석 (인터넷 필요 · 무료 {minimum}화 이상 필요)",
            padding=6,
        )
        box.pack(side="bottom", fill="x", pady=(6, 0))

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Label(row, text="작품 주소 또는 번호", font=_FONT).pack(side="left")
        self.live_var = tk.StringVar()
        entry = ttk.Entry(row, textvariable=self.live_var, font=_FONT)
        entry.pack(side="left", fill="x", expand=True, padx=8)
        entry.bind("<Return>", lambda _event: self._on_analyze())
        self.analyze_button = ttk.Button(row, text="분석", command=self._on_analyze)
        self.analyze_button.pack(side="left")

        self.live_status = ttk.Label(box, text="", font=_FONT_SMALL, foreground="#555555")
        self.live_status.pack(anchor="w", pady=(4, 0))

    def _build_result(self) -> None:
        box = ttk.LabelFrame(self, text="3. 결과", padding=6)
        box.pack(side="bottom", fill="x", pady=(6, 0))

        self.result_title = ttk.Label(box, text="작품을 선택하거나 분석하세요.", font=_FONT_BOLD)
        self.result_title.pack(anchor="w")

        self.result_count = ttk.Label(box, text="—", font=_FONT_BIG)
        self.result_count.pack(anchor="w", pady=(4, 0))
        ttk.Label(
            box,
            text="회차 1편당 예측 구매 건수 (작품 전체 합계가 아닙니다)",
            font=_FONT_SMALL,
            foreground="#555555",
        ).pack(anchor="w")

        row = ttk.Frame(box)
        row.pack(fill="x", pady=(6, 0))
        ttk.Label(row, text="회차 단가(원)", font=_FONT).pack(side="left")
        self.price_var = tk.StringVar(value=str(DEFAULT_UNIT_PRICE))
        price = ttk.Entry(row, textvariable=self.price_var, width=10, font=_FONT)
        price.pack(side="left", padx=8)
        self.price_var.trace_add("write", lambda *_args: self._refresh_revenue())

        self.revenue_label = ttk.Label(row, text="", font=_FONT_BOLD)
        self.revenue_label.pack(side="left", padx=(8, 0))

        ttk.Label(box, text=_PRICE_NOTE, font=_FONT_SMALL, foreground="#555555").pack(
            anchor="w", pady=(4, 0)
        )
        self.band_label = ttk.Label(
            box, text="", font=_FONT, foreground="#b35c00", wraplength=_WRAP, justify="left"
        )
        self.band_label.pack(anchor="w", pady=(4, 0))
        ttk.Label(
            box,
            text=_DISCLAIMER,
            font=_FONT_SMALL,
            foreground="#555555",
            wraplength=_WRAP,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

    # ── 동작 ─────────────────────────────────────────────────────────────

    def _on_search(self) -> None:
        self.tree.delete(*self.tree.get_children())
        hits = search_catalog(self.bundle.catalog, self.search_var.get())
        if hits.empty:
            self.tree.insert("", "end", values=("검색 결과가 없습니다", "", "", ""), tags=("empty",))
            return
        for _, row in hits.iterrows():
            self.tree.insert(
                "",
                "end",
                iid=row["novel_id"],
                values=(
                    row["title"],
                    row["author"],
                    f"{int(row['predicted_paid_events_per_episode']):,}",
                    row["support_band"],
                ),
            )

    def _on_select(self, _event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        matched = self.bundle.catalog[self.bundle.catalog["novel_id"] == selection[0]]
        if matched.empty:
            return
        row = matched.iloc[0]
        self._show(
            PredictionResult(
                ok=True,
                novel_id=row["novel_id"],
                title=row["title"],
                author=row["author"],
                predicted_paid_events_per_episode=int(row["predicted_paid_events_per_episode"]),
                support_band=row["support_band"],
            )
        )

    def _on_analyze(self) -> None:
        novel_id = extract_novel_id(self.live_var.get())
        if novel_id is None:
            self.live_status.config(
                text="작품 번호를 찾지 못했습니다. 작품 주소를 붙여넣거나 번호를 입력하세요.",
                foreground="#c00000",
            )
            return

        self.analyze_button.config(state="disabled")
        self.live_status.config(text=f"작품 {novel_id} 분석 중… (10초쯤 걸립니다)", foreground="#555555")

        # 크롤은 수 초가 걸린다. 메인 스레드에서 돌리면 창이 멈춘 것처럼 보인다.
        threading.Thread(target=self._analyze_worker, args=(novel_id,), daemon=True).start()
        self.after(100, self._poll_worker)

    def _analyze_worker(self, novel_id: str) -> None:
        try:
            client = MunpiaHttpClient(CrawlConfig())
            self._queue.put(predict_live(client, novel_id, self.bundle))
        except Exception:  # 스레드에서 터지면 UI가 영원히 "분석 중"에 머문다.
            self._queue.put(
                PredictionResult(
                    ok=False, novel_id=novel_id, reason="분석 중 예기치 못한 오류가 발생했습니다."
                )
            )

    def _poll_worker(self) -> None:
        try:
            result = self._queue.get_nowait()
        except queue.Empty:
            self.after(100, self._poll_worker)
            return

        self.analyze_button.config(state="normal")
        if result.ok:
            self.live_status.config(text="분석 완료", foreground="#555555")
            self._show(result)
        else:
            self.live_status.config(text=result.reason or "분석에 실패했습니다.", foreground="#c00000")

    # ── 결과 표시 ────────────────────────────────────────────────────────

    def _show(self, result: PredictionResult) -> None:
        self.result = result
        author = f" · {result.author}" if result.author else ""
        self.result_title.config(text=f"{result.title or result.novel_id}{author}")
        self.result_count.config(text=f"{result.predicted_paid_events_per_episode:,}")

        sparse = (result.support_band or "").startswith("희박")
        self.band_label.config(text=_SPARSE_WARNING if sparse else f"신뢰도: {result.support_band}")
        self._refresh_revenue()

    def _refresh_revenue(self) -> None:
        if self.result is None or self.result.predicted_paid_events_per_episode is None:
            return
        try:
            price = int(self.price_var.get().replace(",", "").strip() or 0)
        except ValueError:
            self.revenue_label.config(text="단가는 숫자로 입력하세요")
            return
        revenue = estimate_revenue(self.result.predicted_paid_events_per_episode, price)
        self.revenue_label.config(text=f"→ 회차당 예상 매출 {revenue:,}원")


def run_selftest(report_path: Path) -> None:
    """빌드 산출물이 실제로 동작하는지 창을 띄우지 않고 확인한다.

    배포본은 `console=False`라 표준 출력이 어디에도 보이지 않으므로 결과를 파일에 쓴다.
    특히 **모델 언피클**을 확인하는 것이 목적이다 — `CountVectorizer(analyzer=...)`가
    `service.model_training.genre_tokens`를 참조하는데, PyInstaller가 그 모듈을
    빠뜨리면 배포본에서만 실시간 분석이 죽는다.
    """
    import pandas as pd

    from service.schema import CATEGORICAL_FEATURE_COLUMNS, NUMERIC_FEATURE_COLUMNS

    lines = []
    try:
        bundle = load_bundle(bundle_dir())
        lines.append(f"bundle: {bundle.meta}")
        lines.append(f"catalog: {len(bundle.catalog):,}행")
        lines.append(f"search('바람의 영주'): {len(search_catalog(bundle.catalog, '바람의 영주'))}건")

        sample = pd.DataFrame(
            [{CATEGORICAL_FEATURE_COLUMNS[0]: "판타지,퓨전"}
             | dict(zip(NUMERIC_FEATURE_COLUMNS, [250968, 0.5, 0.7, 4000, 300]))]
        )
        lines.append(f"model.predict: {bundle.model.predict(sample)[0]:,.0f}")
        lines.append("RESULT: OK")
    except Exception as error:
        lines.append(f"RESULT: FAILED — {type(error).__name__}: {error}")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def apply_window_size(root: tk.Tk) -> tuple[int, int]:
    """창을 960×540 기준으로 잡고 화면 중앙에 놓는다.

    화면이 그보다 작으면 화면 크기로 줄인다 — 창이 화면 밖으로 나가면 아래쪽의 단가 입력과
    경고 문구에 손이 닿지 않는다.
    """
    width = min(DESIGN_WIDTH, root.winfo_screenwidth())
    height = min(DESIGN_HEIGHT, root.winfo_screenheight())
    x = max((root.winfo_screenwidth() - width) // 2, 0)
    y = max((root.winfo_screenheight() - height) // 2, 0)
    root.geometry(f"{width}x{height}+{x}+{y}")
    # 이보다 줄이면 아래쪽 경고 문구가 잘린다. 늘리는 건 자유(검색 목록이 넓어진다).
    root.minsize(min(DESIGN_WIDTH, width), min(DESIGN_HEIGHT, height))
    return width, height


def apply_styles(root: tk.Tk) -> None:
    """폰트를 키운 만큼 위젯 치수도 함께 올린다(자동으로 따라오지 않는다)."""
    style = ttk.Style(root)
    if "vista" in style.theme_names():  # 기본 테마보다 위젯 테두리가 또렷하다
        style.theme_use("vista")
    style.configure("Treeview", font=_FONT, rowheight=_ROW_HEIGHT)
    style.configure("Treeview.Heading", font=_FONT_BOLD)
    style.configure("TButton", font=_FONT)
    style.configure("TLabelframe.Label", font=_FONT_BOLD)


def main() -> None:
    if "--selftest" in sys.argv:
        index = sys.argv.index("--selftest")
        target = sys.argv[index + 1] if len(sys.argv) > index + 1 else "selftest.txt"
        run_selftest(Path(target))
        close_splash()
        return

    root = tk.Tk()
    root.title(APP_TITLE)
    apply_window_size(root)
    apply_styles(root)

    try:
        bundle = load_bundle(bundle_dir())
    except Exception as error:
        # 번들이 없으면 빈 창 대신 이유를 보여준다.
        ttk.Label(root, text=f"데이터를 불러오지 못했습니다.\n\n{error}", padding=20).pack()
        close_splash()  # 실패해도 스플래시는 반드시 닫는다(안 닫으면 화면에 남는다)
        root.mainloop()
        return

    App(root, bundle)
    close_splash()
    root.mainloop()


if __name__ == "__main__":
    main()
