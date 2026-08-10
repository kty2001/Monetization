# 문피아 무료→유료 전환 매출 예측

'문피아(Munpia)' 플랫폼의 무료 연재작이 유료로 전환될 때 매출이 어떻게 변화할지 예측하는 프로젝트.

## 배경

유사한 주제를 다룬 참고 프로젝트: [SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN34-2nd-3Team)
(문피아 크롤링 → MySQL 적재 → Streamlit 대시보드 → 유료 전환 "추천 스코어링" 프로젝트)

이 프로젝트는 위 리포지토리의 레이어 구조(entity / repository / service / pages / scripts / research)를 참고하되 다음 두 가지를 다르게 가져간다.

- **목표**: 전환 후보 추천 스코어링이 아니라, 전환 시 **예상 매출액 자체를 예측**하는 것
- **인프라**: MySQL/Docker 대신 **CSV 파일 기반**으로 데이터를 관리, 패키지 관리는 `uv` 사용

## 현재 상태

초기 구조 세팅 단계. 크롤러, 데이터 파이프라인, 예측 모델은 아직 구현되어 있지 않다.

## 디렉토리 구조

```
nonfree/
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

1. 문피아 크롤러 구현 (`clawler/`)
2. 수집 데이터 `data/raw/`에 CSV로 적재
3. 피처 엔지니어링 (`data/processed/`, `service/`)
4. 매출 예측 모델 학습 (`research/`, `scripts/`)
5. 결과 확인용 대시보드 (`pages/`)

## 문서

- [환경설정](docs/01_환경설정.md)
- [프로젝트 개요](docs/02_프로젝트개요.md)
