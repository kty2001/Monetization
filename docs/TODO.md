# TODO

프로젝트 초기 구조 세팅은 완료. 아래는 README/프로젝트개요 문서의 "다음 단계"를 실행 항목으로 정리한 목록.

## 1. 크롤러 (`clawler/`)
- [x] 문피아 무료 연재작 목록/상세 페이지 크롤링 구현
- [x] 조회수, 회차 수, 연재 상태 등 기본 메타데이터 수집
- [x] 수집 결과를 `data/raw/`에 CSV로 저장
- [x] 페이지 범위 확대(전체 목록) 크롤링 **완료** — 48,897건 (2026-08-12, run_id=20260810_231806, 상세는 [크롤러](03_크롤러.md) 참고)
- [x] `pl.serial_end` 샘플 크롤(20건) + 검증 **완료** — 무료 회차 앞쪽 연속(19/20, 예외는 끝의 후기 1화), 무료 회차 중앙값 25화, `purchased_count` 유효(19/20 비-0). → **`N=10` 확정, 회차 최적화 채택** (`data/raw/paid_sample/`, `scripts/analyze_paid_sample.py`)
- [x] `run_crawl`에 `prefix`/`collect_stats` 추가 + `scripts/crawl_munpia.py`에 `--section`/`--prefix`/`--collect-stats` — 별도 `paid_runner.py` 없이 기존 러너 재사용
- [x] `--start-page` 추가 (`iter_list_page_items`/두 러너/두 스크립트) — `--resume` 시 앞 페이지 재스캔에 20분 이상 버리던 문제 해결
- [x] `--max-pages 0`/`--novel-limit 0` = 제한 없음 — 기본값 1인 `--max-pages`를 빠뜨리면 조용히 20건만 수집하고 정상 종료하던 문제(문서 예시도 틀려 있었음)
- [x] `fetch_novel_bundle`/`run_crawl`/`--free-chapters-only` 추가 (첫 유료 회차에서 중단 — 크롤 9시간대 → 2시간대)
- [x] 워치독 `scripts/watch_and_resume.ps1` — 프로세스 감시 + 정체 감지 + `--start-page` 자동 계산 + 무한 재시작 방지
- [x] **유료 전환작 라벨 크롤 실행** **완료** — `pl.serial_end` 9,252건 / 234,058회차 (2026-08-12, run_id=`20260812_174443`, `data/raw/paid/`)
- [x] `scripts/analyze_paid_sample.py --data-dir data/raw/paid`로 N=10·최적화 가정 재확인 **완료** — 연속성 위반 0건, 무료 회차 중앙값 25, `N=10` 시 97.4% 사용 가능, 타겟 비-0 99.7%
- [x] **학습셋/추론셋 지지구간 재측정 완료** (2026-08-13) — 범위 외삽은 44.4% → **0.6%로 해소**, 그러나 무료작 84%가 학습셋 5분위수 미만이라 **밀도 불일치는 잔존**. 대응 방침은 [로드맵](04_로드맵.md) 핵심 결정 사항 참고
- [ ] `pl.serial`(진행 중 1,212건) 크롤 — 학습 제외·정성 검증용이라 **후순위**
- [x] nv.free 좋아요/선호작(구독) 통계 백필(`scripts/crawl_munpia_stats.py`) **완료** — 48,864건 (`data/raw/stats/`)
- [x] 무료작 **2시점째 스냅샷** 확보 (2026-08-12, run_id=`20260812_121713`) — 1시점(2026-08-11)과 21.4시간 간격
- [x] **스냅샷 주기 확정** (2026-08-13) — **월 1회 / 목록 앞 200페이지**(`--max-pages 200`). 일 단위는 지지구간 작품의 87%가 전 필드 0인 노이즈였고, 목록이 최신순 정렬(스피어만 0.998)이라 30일 내 갱신분 99%가 첫 126페이지 안. 회당 1~3시간 → 3분대. 근거·자동화 설계는 [크롤러](03_크롤러.md) "정기 스냅샷 운영" 참고
- [ ] `scripts/monthly_snapshot.ps1` 생성 + 작업 스케줄러 등록 (스크립트 내용·`schtasks` 명령은 문서에 기재 완료, 실행만 남음)

## 2. 데이터 파이프라인 (`data/`, `repository/`, `service/`)
- [x] `repository/`에 `prefix` 옵션, `NovelStats` 저장 메서드 추가
- [x] `entity/novel_stats.py`(목록 API의 구매/대여 수 등 매핑) 구현
- [x] ~~유료 전환작 라벨 크롤러 (`clawler/paid_runner.py`)~~ — 별도 러너 대신 `run_crawl` 확장으로 해결
- [x] `data/raw/` → `data/processed/` 정제 로직 (`service/raw_loader.py`, `novel_features.py`, `target_builder.py`, `schema.py` + `scripts/build_processed_dataset.py`)
- [x] 피처 엔지니어링: **앞 10화 기준** — `free_views_1_10`, `retention_1_to_10`, `retention_1_to_3`, `likes_1_10`, `comments_1_10`. 추론셋 **11,189건**, 학습셋 **8,990건**(`labeled_dataset_20260813.csv`, 2026-08-13) 생성 완료
- [x] `snapshot_date`(YYYYMMDD) 기반 누적 저장
- [x] **범주형 피처 결함 수정** (2026-08-13) — `serialization_status`(학습 "완결" 100% / 추론 "연재중" 100%로 분할과 교락)와 `tags`(결측률 56.2% vs 35.0%)를 피처에서 제거, `genres`는 토큰 단위 multi-hot으로 전환. 재발 방지 테스트 추가. 두 데이터셋 재생성 완료(행수 불변)
- [ ] 제목의 U+FEFF 제거 — 현재 피처에 제목을 쓰지 않아 보류. 대시보드에서 제목을 표시할 때 처리
- [ ] novels↔novel_stats join 정책 결정 (2시점 기준 94건 결측)

## 3. 엔티티/모델 정의 (`entity/`)
- [x] 작품/회차 데이터 모델(DTO) 정의 (`Novel`, `Episode`)
- [x] 유료 전환작 통계 모델 정의 (`NovelStats`)
- [x] `Novel`에 `like_count`/`preference_count` 추가 — 진행 중인 크롤을 재개하며 스키마가 중간에 바뀌어 `novels_20260810_231806.csv`가 11필드/13필드로 깨졌던 것을 발견해 복구(구 36,145행은 두 컬럼 NaN, 신규 12,752행은 값 있음). 재발 방지로 `repository/csv_writer.append_csv`에 헤더-스키마 불일치 시 예외를 던지는 가드 추가(`tests/test_csv_writer.py`)

## 4. 구매수 예측 모델 (`research/`, `scripts/`)
- [x] `research/` ML 실험 **완료** — `01_eda.ipynb` / `02_baseline_and_linear.ipynb` / `03_tree_ensembles.ipynb` (로직은 `service/model_training.py`, 노트북은 호출만)
- [x] 학습 파이프라인 `scripts/` 정리 **완료** — `train_revenue_model.py`(학습+pickle 저장+지표 JSON) / `predict_conversion_revenue.py`(추론+밴드 라벨)
- [x] 모델 검증 **완료** — `HistGradientBoostingRegressor` 채택. logRMSE 0.9036 / logR² 0.827 / MdAPE 51.3% / Spearman 0.892. `free_views_1_10` 단일회귀 베이스라인 대비 **18.7% 개선**(CV 표준편차의 17배)
- [x] **DL 도입 불필요** 판정 — 위 개선폭이 노이즈로 설명되지 않음([로드맵 C](04_로드맵.md))
- [x] 선택 편향 대응 — `support_band` 컬럼(정상 16.0% / 희박 84.0%)을 예측 출력에 포함. 대시보드에서 "전환 성공 시 조건부 기댓값"으로 표기하는 것은 5절에서
- [x] **타겟 정의 오류 수정** (2026-08-13) — `nvSumPurchased`는 **작품 전체 누적** 구매수인데 회차당으로 표시해 회차당 매출이 100배 넘게 부풀려졌다(실사용에서 회차당 1,110만원 발생 → 수정 후 61,600원). 유료 회차 수로 나눈 `target_paid_events_per_episode`로 전환. **성능도 함께 개선**: logRMSE 0.9036 → 0.6947, MdAPE 51.3% → 40.6%, Spearman 0.892 → 0.919
- [x] **테스트 데이터 성능 파악 완료** (2026-08-13) — holdout 1,798건 기준 ±25% 이내 26.5% / 2배 이내 58.7% / 5배 이내 92.5%. 하위 20% 1.56배 과대, 상위 20% 0.56배 과소예측(평균 회귀). 상세는 [모델 명세](06_모델.md)
- [x] **하이퍼파라미터 튜닝 여력 조사 완료** — 25조합 랜덤서치로 CV logRMSE 0.9221 → 0.9172(0.5%)에 그쳐 **적용 보류**. 병목은 하이퍼파라미터가 아니라 피처
- [ ] **`N` 선택 미결** — N=20이 8.2% 개선(logRMSE 0.9036 → 0.8294, MdAPE 51.3% → 47.4%)이지만 검색 대상이 11,189 → 5,737로 절반이 된다. N=10 유지 / N=20 전환 / 2단 구성 중 결정 필요
- [ ] 신규 피처 탐색 — 회차당 좋아요·댓글 비율, 조회수 감소 기울기, 연재 주기(`published_at` 간격) 등
- [ ] `tags` 상위 K개 토큰 multi-hot 재검토 (현재 결측률 시프트로 제외)

> 매출(KRW)은 모델이 예측하지 않는다. `예상 매출 = 예측 구매수 × 회차 단가`이고, 단가는 작가별 계약에 따라 달라 크롤 불가하므로 앱에서 사용자가 입력받아 곱한다. 단가는 학습·피처에 개입하지 않는다.

## 5. 배포용 데스크톱 앱 (`app/`)
- [x] ~~Streamlit 대시보드~~ **폐기** — 수요자가 비전공자 작가인데 `streamlit run`이 Python 설치를 전제한다. `pages/`·`streamlit` 의존성 제거
- [x] **PyInstaller + Tkinter 앱 구현 완료** (2026-08-13) — 조회(11,189건 스냅샷) + 작품 주소 실시간 크롤·예측
- [x] **onefile 단일 exe로 전환** — `dist/MunpiaRevenue.exe` **72.1MB** 하나만 전달하면 실행된다(onedir은 `_internal/` 151MB가 있어야 해 exe만 넘기면 exit -1로 실패했다). 대가로 **매 실행 7~8초**(onedir 2.3초)라 스플래시를 띄운다(0.4초 만에 표시)
- [ ] 실행 속도가 문제되면 onedir + zip으로 되돌리는 것을 재검토 (전달 편의 ↔ 실행 속도 교환)
- [x] **회차 단가 입력 위젯** → `예측 구매수 × 단가` 실시간 환산
- [x] `support_band` 경고 · "전환 성공 시 조건부 기댓값" 문구 UI 노출 + 작가용 `사용법.txt` 동봉
- [x] 빌드 자동화 `scripts/build_desktop_app.ps1` (번들 → 빌드 → 자체 점검 → 압축)
- [x] **실사용 피드백 반영** (2026-08-13) — 창 1920×1080 기준 + 폰트 확대(본문 10→13, 예측 숫자 20→34), 검색 범위 문구를 사실대로 수정(예측 날짜를 수집 시점으로 잘못 표시하고 있었음)
- [ ] 코드 서명 인증서 — 없으면 첫 실행 시 SmartScreen "알 수 없는 게시자" 경고가 계속 뜬다(현재는 `사용법.txt` 안내로 대응)
- [ ] 스냅샷 갱신 시 재빌드·재배포 절차 — 자동 업데이트 없음

## 6. 테스트 (`tests/`)
- [x] 크롤러 핵심 로직 테스트 (`entity`, `repository`, `clawler`) — **64개 통과**
- [x] 데이터 품질 검증 (`service/data_quality.py`, `scripts/validate_raw_data.py`) — `novel_stats` 검증, novels↔stats 커버리지, run_id 짝짓기 추가
- [x] CSV append 스키마 가드 테스트 (`tests/test_csv_writer.py`)
- [x] `detail_crawler`/`runner` 테스트 추가 (`tests/test_detail_crawler.py`, `tests/test_runner.py`) — 스키마 변경 감지·페이지네이션·limit/skip/abort/resume·`free_chapters_only`
- [x] 파이프라인(`service/`) 테스트 — `test_episode_features.py`, `test_target_builder.py`, `test_schema.py`, `test_raw_loader.py`
- [x] 모델링 테스트 (`tests/service/test_model_training.py`) — fit→predict, log1p 역변환, 미학습 장르 토큰, pickle 직렬화, 층화 분할, 밴드 라벨링
- [x] 앱 로직 테스트 (`tests/service/test_inference.py`) — URL/번호 파싱, 카탈로그 검색, 실시간 예측(정상·10화 미만·작품 없음·차단). 전체 **125개 통과**
- [x] `leading_free_episodes` 버그 수정 — 앞 N화로 자른 뒤 세어 **항상 10**이 나오고 있었다(메타데이터로서 정보량 0). 자르기 전에 세도록 고쳐 학습셋 중앙값 25 / 무료작 20으로 정상화. 피처가 아니라 모델에는 영향 없음

상세 설계는 [로드맵](04_로드맵.md) 참고.

## 참고
- [프로젝트 개요](02_프로젝트개요.md)
- [환경설정](01_환경설정.md)
- [크롤러](03_크롤러.md)
- [로드맵](04_로드맵.md)
- [데이터 사전](05_데이터사전.md)
- [모델 명세](06_모델.md)
