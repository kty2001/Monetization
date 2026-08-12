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
예상 매출(KRW) = 예측 구매수 × 회차 단가
                  └ 모델이 예측     └ 사용자가 대시보드에서 입력
```

- **모델이 예측하는 것**: 유료 전환작 목록 API의 구매수(`nvSumPurchased`) — 무료 연재 시점의 지표(조회수/좋아요/선호작/이탈률 등)로부터 회귀
- **모델이 예측하지 않는 것**: 회차 단가. 단가는 학습·피처에 일절 개입하지 않고, 대시보드에서 입력받아 마지막에 곱하기만 한다. 상수배라 작품 간 순위에도 영향이 없다.

설계 배경과 주의사항(피처 누수·선택 편향 등)은 [로드맵](docs/04_로드맵.md) 참고.

## 현재 상태

- 문피아 크롤러(`clawler/`, `entity/`, `repository/`) 구현 완료, `scripts/crawl_munpia.py`로 실행
- 무료 자유연재 전체 목록 크롤링 **완료** (48,897건) + 좋아요/선호작 통계 백필 **완료** (48,864건)
- 다음 단계: 유료 전환작(`pl.serial`/`pl.serial_end`) 라벨 크롤러 → 데이터 파이프라인(`data/processed/`) → 예측 모델(`research/`, `scripts/`) → 대시보드(`pages/`)

자세한 내용은 [크롤러](docs/03_크롤러.md), [TODO](docs/TODO.md) 참고.

## 디렉토리 구조

```
Monetization/
├── pyproject.toml     # uv 프로젝트 설정
├── clawler/            # 문피아 크롤링 코드
├── data/
│   ├── raw/             # 크롤링 원본 CSV
│   └── processed/       # 가공된 CSV
├── docs/               # 프로젝트 문서
├── entity/             # 데이터 모델/DTO
├── pages/              # Streamlit 페이지
├── repository/         # CSV 기반 데이터 접근 계층
├── research/           # 분석/모델 실험 노트북
├── scripts/            # 데이터 처리·학습 스크립트
├── service/            # 핵심 비즈니스 로직
└── tests/              # 테스트
```

## 다음 단계

1. ~~문피아 크롤러 구현 (`clawler/`)~~ ✅
2. ~~수집 데이터 `data/raw/`에 CSV로 적재~~ ✅ (무료 자유연재 48,897건)
3. 유료 전환작 라벨 크롤러 (`clawler/paid_runner.py`)
4. 피처 엔지니어링 (`data/processed/`, `service/`)
5. 구매수 예측 모델 학습 (`research/`, `scripts/`)
6. 결과 확인용 대시보드 (`pages/`) — 단가 입력 → 예상 매출 환산

## 문서

- [환경설정](docs/01_환경설정.md)
- [프로젝트 개요](docs/02_프로젝트개요.md)
- [크롤러](docs/03_크롤러.md)
- [로드맵](docs/04_로드맵.md)
- [데이터 사전](docs/05_데이터사전.md)
- [TODO](docs/TODO.md)
