# 문피아 무료→유료 전환 매출 예측

'문피아(Munpia)' 플랫폼의 무료 연재작이 유료로 전환될 때 매출이 어떻게 변화할지 예측하는 프로젝트.

## 배경

유사한 주제를 다룬 참고 프로젝트: [SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team)
(문피아 크롤링 → MySQL 적재 → Streamlit 대시보드 → 유료 전환 "추천 스코어링" 프로젝트)

위 리포지토리의 레이어 구조(entity / repository / service / scripts / research)를 참고하되 다음 두 가지를 다르게 가져감.

- **목표**: 전환 후보 추천 스코어링이 아니라, 전환 시 **예상 매출을 예측**하는 것
- **인프라**: MySQL/Docker 대신 **CSV 파일 기반**으로 데이터를 관리, 패키지 관리는 `uv` 사용

## 매출을 어떻게 예측하나

문피아는 실제 매출(KRW)을 공개하지 않고, 회차 단가는 작가별 계약에 따라 달라 크롤로 확보할 수 없음. 그래서 매출을 통째로 학습하지 않고 둘로 나눔.

```
회차당 예상 매출(KRW) = 회차당 예측 구매수 × 회차 단가
                         └ 모델이 예측        └ 사용자가 앱에서 입력

작품 전체 매출        = 회차당 예상 매출 × 유료 연재 회차 수
```

- **모델이 예측하는 것**: **회차 1편당** 구매 건수 — 유료 전환작 목록 API의 `nvSumPurchased`(작품 전체 누적)를 유료 회차 수로 나눈 값을, 무료 연재 시점의 지표(조회수/좋아요/이탈률 등)로부터 회귀
- **모델이 예측하지 않는 것**: 회차 단가. 단가는 학습·피처에 일절 개입하지 않고, 앱에서 입력받아 마지막에 곱하기만 함. 상수배라 작품 간 순위에도 영향 없음

설계 배경과 주의사항(피처 누수·선택 편향 등)은 [로드맵](docs/04_로드맵.md) 참고.

## 현재 상태

전 단계 구현 완료. 남은 과제는 [TODO](docs/TODO.md) 참고.

| 단계 | 상태 | 규모 |
|---|---|---|
| 크롤러 (`clawler`/`entity`/`repository`) | 완료 | — |
| 무료 자유연재(`nv.free`) 크롤 | 완료 | 48,897작품 / 431,782회차 |
| 목록 통계 스냅샷 | 완료 | 2시점 확보, 이후 월 1회 운영 |
| 유료 전환작(`pl.serial_end`) 라벨 크롤 | 완료 | 9,252작품 / 234,058회차 |
| 데이터 파이프라인 (`service`) | 완료 | 학습셋 8,990건 / 추론셋 11,189건 |
| 구매수 예측 모델 | 완료 | logR² 0.869 / MdAPE 40.6% / Spearman 0.919 |
| 배포용 데스크톱 앱 (`app`) | 완료 | `dist/MunpiaRevenue.exe` 72.1MB |
| 테스트 | 통과 | 129개 |

모델은 `HistGradientBoostingRegressor`로 **회차당 구매 건수**를 예측하며, 단일회귀 베이스라인 대비 19.7% 개선됨([모델 명세](docs/06_모델.md)). 앱은 Streamlit 대신 PyInstaller+Tkinter로 만들어 조회와 작품 주소 실시간 분석을 제공함([로드맵 D](docs/04_로드맵.md)).

## How to Use

Python 3.13 이상과 [uv](https://docs.astral.sh/uv/getting-started/installation/)가 필요함. **`data/`는 git 제외 대상이라 클론 직후에는 비어 있으므로 크롤부터 실행해야 함.**

```bash
# 설치
git clone <repository-url>
cd Monetization
uv sync
uv run pytest

# 1. 데이터 수집
uv run python scripts/crawl_munpia.py --max-pages 0 --novel-limit 0 --delay 0.8 --resume
uv run python scripts/crawl_munpia.py --section pl.serial_end --prefix paid_ \
  --collect-stats --free-chapters-only --max-pages 0 --novel-limit 0 --delay 0.8 \
  --output-dir data/raw/paid
uv run python scripts/crawl_munpia_stats.py --max-pages 200 --delay 0.8

# 2. 검증
uv run python scripts/validate_raw_data.py
uv run python scripts/validate_raw_data.py --prefix paid_ --data-dir data/raw/paid --stats-dir data/raw/paid

# 3. 데이터셋 생성
uv run python scripts/build_processed_dataset.py --free
uv run python scripts/build_processed_dataset.py --labeled \
  --data-dir data/raw/paid --stats-dir data/raw/paid --prefix paid_

# 4. 학습과 추론
uv run python scripts/train_revenue_model.py
uv run python scripts/predict_conversion_revenue.py
```

```powershell
# 5. 배포용 exe 빌드 (Windows)
powershell -File scripts/build_desktop_app.ps1   # → dist/MunpiaRevenue.exe
```

⚠️ `--max-pages 0`을 빠뜨리면 조용히 20건만 수집하고 정상 종료함(기본값 1).

요구사항·옵션·중단 재개·문제 해결은 **[실행 가이드](docs/07_실행가이드.md)** 참고.

## 디렉토리 구조

```
Monetization/
├── pyproject.toml       # uv 프로젝트 설정
├── clawler/             # 문피아 크롤링 코드 (HTTP·오케스트레이션)
├── entity/              # 데이터 모델/DTO
├── repository/          # CSV 기반 데이터 접근 계층
├── service/             # 피처 엔지니어링·학습·추론 로직
├── scripts/             # 크롤·검증·데이터셋·학습·빌드 스크립트
├── app/                 # 배포용 데스크톱 앱 (Tkinter + PyInstaller)
├── research/            # 분석/모델 실험 노트북
├── data/
│   ├── raw/             # 크롤링 원본 CSV (git 제외)
│   └── processed/       # 가공 CSV·모델·예측 (git 제외)
├── docs/                # 프로젝트 문서
└── tests/               # 테스트
```

## 문서

- [환경설정](docs/01_환경설정.md) — uv 기반 개발 환경
- [프로젝트 개요](docs/02_프로젝트개요.md) — 문제 정의와 접근 방향
- [크롤러](docs/03_크롤러.md) — 실행 옵션·API 조사 결과·재개 동작
- [로드맵](docs/04_로드맵.md) — 설계 결정과 그 근거
- [데이터 사전](docs/05_데이터사전.md) — CSV 컬럼 정의
- [모델 명세](docs/06_모델.md) — 학습된 피처·하이퍼파라미터·성능·한계
- [실행 가이드](docs/07_실행가이드.md) — 클론부터 exe 빌드까지 단계별 상세
- [TODO](docs/TODO.md) — 남은 작업
