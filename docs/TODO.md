# TODO

프로젝트 초기 구조 세팅은 완료. 아래는 README/프로젝트개요 문서의 "다음 단계"를 실행 항목으로 정리한 목록.

## 1. 크롤러 (`clawler/`)
- [x] 문피아 무료 연재작 목록/상세 페이지 크롤링 구현
- [x] 조회수, 회차 수, 연재 상태 등 기본 메타데이터 수집
- [x] 수집 결과를 `data/raw/`에 CSV로 저장
- [x] 페이지 범위 확대(전체 목록) 크롤링 **완료** — 48,897건 (2026-08-12, run_id=20260810_231806, 상세는 [크롤러](03_크롤러.md) 참고)
- [ ] 유료 전환작(`pl.serial`/`pl.serial_end`) 라벨 데이터 크롤러 — 다음 단계 (설계는 [로드맵](04_로드맵.md) 참고)
- [x] nv.free 좋아요/선호작(구독) 통계 백필(`scripts/crawl_munpia_stats.py`) **완료** — 48,864건 (`data/raw/stats/`)

## 2. 데이터 파이프라인 (`data/`, `repository/`, `service/`)
- [x] `repository/`에 `prefix` 옵션, `NovelStats` 저장 메서드 추가
- [x] `entity/novel_stats.py`(목록 API의 구매/대여 수 등 매핑) 구현
- [ ] 유료 전환작 라벨 크롤러 (`clawler/paid_runner.py`, `scripts/crawl_munpia_paid.py`)
- [ ] `data/raw/` → `data/processed/` 정제 로직 작성 (`service/`)
- [ ] 피처 엔지니어링: 무료 회차 조회수/좋아요/댓글, 이탈률(`view_retention_ratio`) 등
- [ ] 여러 시점 데이터 수집을 위한 `snapshot_date` 기반 누적 저장

## 3. 엔티티/모델 정의 (`entity/`)
- [x] 작품/회차 데이터 모델(DTO) 정의 (`Novel`, `Episode`)
- [x] 유료 전환작 통계 모델 정의 (`NovelStats`)
- [x] `Novel`에 `like_count`/`preference_count` 추가 — 진행 중인 크롤을 재개하며 스키마가 중간에 바뀌어 `novels_20260810_231806.csv`가 11필드/13필드로 깨졌던 것을 발견해 복구(구 36,145행은 두 컬럼 NaN, 신규 12,752행은 값 있음). 재발 방지로 `repository/csv_writer.append_csv`에 헤더-스키마 불일치 시 예외를 던지는 가드 추가(`tests/test_csv_writer.py`)

## 4. 매출 예측 모델 (`research/`, `scripts/`)
- [ ] `research/`에서 ML(회귀) 모델 먼저 실험 (타겟: 구매수 `target_paid_events`, 유료 전환 시 매출 프록시)
- [ ] 학습 파이프라인을 `scripts/`에 정리
- [ ] 모델 검증 및 성능 개선 (베이스라인: 평균/중앙값, `total_free_views` 단일회귀)
- [ ] ML 성능이 부족하다고 판단되면 DL 접근 도입 검토

## 5. 대시보드 (`pages/`)
- [ ] Streamlit 기반 예측 결과 확인용 대시보드 구현 (`st.navigation` 3페이지: 개요/예측결과/모델성능)

## 6. 테스트 (`tests/`)
- [x] 크롤러 핵심 로직 테스트 (`entity`, `repository`, `clawler`) — 41개 통과
- [x] 데이터 품질 검증 (`service/data_quality.py`, `scripts/validate_raw_data.py`)
- [x] CSV append 스키마 가드 테스트 (`tests/test_csv_writer.py`)
- [ ] 파이프라인(`service/`)·모델링 테스트 작성

상세 설계는 [로드맵](04_로드맵.md) 참고.

## 참고
- [프로젝트 개요](02_프로젝트개요.md)
- [환경설정](01_환경설정.md)
- [크롤러](03_크롤러.md)
- [로드맵](04_로드맵.md)
- [데이터 사전](05_데이터사전.md)
