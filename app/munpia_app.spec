# PyInstaller 스펙 — 배포용 데스크톱 앱 빌드.
#
#     uv run pyinstaller app/munpia_app.spec --noconfirm
#
# **onefile**로 묶는다. 산출물이 exe 하나뿐이라 작가에게 파일 하나만 보내면 된다.
# (onedir은 exe가 실행기일 뿐이고 알맹이가 _internal/ 151MB에 있어 폴더째 보내야 했다.)
#
# 대가: 첫 실행에서 ~150MB를 %TEMP%에 푸느라 10초 안팎이 걸린다(두 번째부터는 OS 파일
# 캐시 덕에 1~2초). 그 사이 아무 반응이 없으면 작가가 계속 더블클릭하므로 스플래시를 띄운다.
from pathlib import Path

ROOT = Path(SPECPATH).parent
BUNDLE = ROOT / "app" / "bundle"
SPLASH_IMAGE = ROOT / "app" / "splash.png"

if not (BUNDLE / "catalog.csv").exists():
    raise SystemExit(
        f"{BUNDLE}에 번들이 없습니다. 먼저 실행하세요:\n"
        "    uv run python scripts/build_app_bundle.py"
    )

if not SPLASH_IMAGE.exists():
    raise SystemExit(
        f"{SPLASH_IMAGE}가 없습니다. 먼저 실행하세요:\n"
        "    uv run python scripts/make_splash.py"
    )

a = Analysis(
    [str(ROOT / "app" / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(BUNDLE), "bundle")],
    hiddenimports=[
        # 모델 pkl을 언피클할 때 CountVectorizer(analyzer=...)가 이 모듈의
        # genre_tokens를 참조한다. main.py에서 직접 import하지 않으므로 명시해야 한다.
        "service.model_training",
        "sklearn.ensemble._hist_gradient_boosting.predictor",
        "sklearn.utils._typedefs",
        "sklearn.utils._heap",
        "sklearn.utils._sorting",
        "sklearn.utils._vector_sentinel",
    ],
    excludes=[
        # 앱이 쓰지 않는 무거운 패키지를 빼 용량을 줄인다.
        "matplotlib",
        "IPython",
        "jupyter",
        "ipykernel",
        "notebook",
        "pytest",
        "streamlit",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

splash = Splash(
    str(SPLASH_IMAGE),
    binaries=a.binaries,
    datas=a.datas,
    always_on_top=False,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
    a.binaries,
    a.datas,
    name="MunpiaRevenue",
    console=False,  # 작가에게 검은 콘솔 창을 띄우지 않는다.
    upx=False,
    onefile=True,
)
