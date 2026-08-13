"""onefile 첫 실행 대기용 스플래시 이미지를 만든다.

    uv run python scripts/make_splash.py

onefile 배포본은 **매 실행마다** ~150MB를 임시 폴더에 푸느라 메인 창이 뜨기까지 7~8초가
걸린다(실측: 1회차 7.6초 / 2회차 7.2초 — 캐시가 붙어도 압축 해제 자체는 매번 한다).
그동안 아무 반응이 없으면 작가가 실행이 안 된 줄 알고 계속 더블클릭해 여러 개가 뜬다.
스플래시는 0.4초 만에 뜬다.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "app" / "splash.png"

WIDTH, HEIGHT = 460, 160
BACKGROUND = "#f7f7f7"
BORDER = "#c8c8c8"
TITLE_COLOR = "#1a1a1a"
BODY_COLOR = "#555555"


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    name = "malgunbd.ttf" if bold else "malgun.ttf"
    try:
        return ImageFont.truetype(name, size)
    except OSError:  # 맑은 고딕이 없는 환경(비Windows)에서는 기본 폰트로 떨어진다
        return ImageFont.load_default()


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, 0), (WIDTH - 1, HEIGHT - 1)], outline=BORDER, width=1)

    draw.text((28, 34), "문피아 유료 전환 매출 예측", font=_font(20, bold=True), fill=TITLE_COLOR)
    draw.text((28, 76), "프로그램을 준비하고 있습니다…", font=_font(14), fill=BODY_COLOR)
    draw.text((28, 102), "10초쯤 걸립니다. 잠시만 기다려 주세요.", font=_font(13), fill=BODY_COLOR)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUTPUT)
    print(f"저장: {OUTPUT} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    sys.exit(main())
