# 문피아 무료→유료 전환 매출 예측

'문피아(Munpia)' 플랫폼의 무료 연재작이 유료로 전환될 때 매출이 어떻게 변화할지 예측하는 프로젝트.

## 배경

유사한 주제를 다룬 참고 프로젝트: [SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team)
(문피아 크롤링 → MySQL 적재 → Streamlit 대시보드 → 유료 전환 "추천 스코어링" 프로젝트)

이 프로젝트는 위 리포지토리의 레이어 구조(entity / repository / service / pages / scripts / research)를 참고하되 다음 두 가지를 다르게 가져간다.

- **목표**: 전환 후보 추천 스코어링이 아니라, 전환 시 **예상 매출을 예측**하는 것
- **인프라**: MySQL/Docker 대신 **CSV 파일 기반**으로 데이터를 관리, 패키지 관리는 `uv` 사용

## 매출을 어떻게 예측하나

문피아는 실제 매출(KRW)을 공개하지 않고, 회차 단가는 작가별 계약에 따라 다르므로 크롤로 확보할 수 없다. 그래서 매출을 통째로 학습하지 않고 둘로 나눈다.

```
회차당 예상 매출(KRW) = 회차당 예측 구매수 × 회차 단가
                         └ 모델이 예측        └ 사용자가 앱에서 입력

작품 전체 매출        = 회차당 예상 매출 × 유료 연재 회차 수
```

- **모델이 예측하는 것**: **회차 1편당** 구매 건수 — 유료 전환작 목록 API의 `nvSumPurchased`(작품 전체 누적)를 유료 회차 수로 나눈 값을, 무료 연재 시점의 지표(조회수/좋아요/이탈률 등)로부터 회귀
- **모델이 예측하지 않는 것**: 회차 단가. 단가는 학습·피처에 일절 개입하지 않고, 대시보드에서 입력받아 마지막에 곱하기만 한다. 상수배라 작품 간 순위에도 영향이 없다.

설계 배경과 주의사항(피처 누수·선택 편향 등)은 [로드맵](docs/04_로드맵.md) 참고.

## 현재 상태

- 문피아 크롤러(`clawler/`, `entity/`, `repository/`) 구현 완료, `scripts/crawl_munpia.py`로 실행 (`--section`으로 무료/유료 섹션 전환)
- 무료 자유연재 전체 크롤링 **완료** (48,897작품 / 431,782회차) + 좋아요·선호작 통계 스냅샷 2시점 확보
- 유료 전환작(`pl.serial_end`) 라벨 크롤 **완료** — 9,252작품 / 234,058회차. `N=10` 가정 전수 재확인 ([로드맵](docs/04_로드맵.md) A절)
- 데이터 파이프라인 **완료** — 학습셋 8,990건 / 추론셋 11,189건 (`data/processed/`)
- 구매수 예측 모델 **완료** — `HistGradientBoostingRegressor`로 **회차당 구매 건수** 예측. logR² 0.869 / MdAPE 40.6% / Spearman 0.919, 단일회귀 베이스라인 대비 19.7% 개선 ([모델 명세](docs/06_모델.md))
- 작가 배포용 **데스크톱 앱 완료** — Streamlit 대신 PyInstaller+Tkinter. 조회 + 작품 주소 실시간 분석, `dist/MunpiaRevenue.zip` 72.5MB ([로드맵 D](docs/04_로드맵.md))

자세한 내용은 [크롤러](docs/03_크롤러.md), [TODO](docs/TODO.md) 참고.

## 디렉토리 구조

```
Monetization/
├── pyproject.toml     # uv 프로젝트 설정
├── clawler/            # 문피아 크롤링 코드
├── data/
│   ├── raw/             # 크롤링 원본 CSV
│   └── processed/       # 가공된 CSV
├── app/                # 배포용 데스크톱 앱 (Tkinter + PyInstaller)
├── docs/               # 프로젝트 문서
├── entity/             # 데이터 모델/DTO
├── repository/         # CSV 기반 데이터 접근 계층
├── research/           # 분석/모델 실험 노트북
├── scripts/            # 데이터 처리·학습 스크립트
├── service/            # 핵심 비즈니스 로직
└── tests/              # 테스트
```

## 다음 단계

1. ~~문피아 크롤러 구현 (`clawler/`)~~ ✅
2. ~~수집 데이터 `data/raw/`에 CSV로 적재~~ ✅ (무료 자유연재 48,897건)
3. ~~유료 전환작 라벨 크롤 (`--section pl.serial_end`)~~ ✅ (9,252건)
4. ~~피처 엔지니어링 (`data/processed/`, `service/`)~~ ✅
5. ~~구매수 예측 모델 학습 (`research/`, `scripts/`)~~ ✅
6. ~~작가 배포용 앱 (`app/`) — 단가 입력 → 예상 매출 환산~~ ✅

## 앱 빌드

```powershell
powershell -File scripts/build_desktop_app.ps1   # → dist/MunpiaRevenue.exe
```

번들 생성 → 스플래시 이미지 → PyInstaller onefile 빌드 → 빌드본 자체 점검(`--selftest`)을 한 번에 실행한다. 작가에게는 **`MunpiaRevenue.exe` 파일 하나만** 전달하면 되고, 설치도 압축 풀기도 필요 없다(Python 설치 불필요).

단일 exe라 실행할 때마다 내부 파일을 푸느라 **매번 7~8초**가 걸리며, 그동안 스플래시가 뜬다(0.4초 만에 표시). 서명되지 않은 exe라 첫 실행 시 SmartScreen 경고가 뜨며, 대응 절차는 `dist/사용법.txt`에 있다.

## 문서

- [환경설정](docs/01_환경설정.md)
- [프로젝트 개요](docs/02_프로젝트개요.md)
- [크롤러](docs/03_크롤러.md)
- [로드맵](docs/04_로드맵.md)
- [데이터 사전](docs/05_데이터사전.md)
- [모델 명세](docs/06_모델.md) — 실제 학습된 피처·하이퍼파라미터·성능·한계
- [TODO](docs/TODO.md)
