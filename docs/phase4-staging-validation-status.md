# Phase 4 Staging Validation 현황 보고

**작성일:** 2026-03-31
**상태:** 🔄 Staging 검증 진행 중

---

## 📋 현재 상태 요약

### ✅ 완료된 작업

1. **Phase 4 개발 완료**
   - Minimal Review Console UI 구현 완료
   - End-to-End Integration Tests 100% PASS (13/13)
   - 문서화 완료 (completion report, operator guide)

2. **Staging 환경 준비 완료**
   - 실제 한국 쇼핑몰 스타일 샘플 데이터 20개 생성
   - 다양한 카테고리 (주방용품, 전자제품, 생활가전, 스포츠용품 등)
   - PASS/HOLD 혼합 (PASS: 17개, HOLD: 3개)
   - 이미지 2~4개씩 포함

### 📦 생성된 샘플 리뷰 항목 (20개)

| # | 상품명 | Score | Decision | Images |
|---|--------|-------|----------|---------|
| 1 | 프리미엄 스테인리스 텀블러 500ml 보온보냉 | 85 | PASS | 4 |
| 2 | 무선 블루투스 이어폰 노이즈캔슬링 | 78 | PASS | 3 |
| 3 | LED 스탠드 조명 무선충전 스마트 | 82 | PASS | 4 |
| 4 | 프리미엄 요가매트 10mm TPE 친환경 | 88 | PASS | 3 |
| 5 | 전기 그릴 가정용 무연 실내 BBQ | 75 | HOLD | 3 |
| 6 | USB 미니 가습기 초음파 휴대용 | 80 | PASS | 2 |
| 7 | 스마트 체중계 블루투스 체지방 측정 | 72 | HOLD | 3 |
| 8 | 휴대용 손선풍기 USB 충전식 미니 | 83 | PASS | 2 |
| 9 | 무선 마우스 블루투스 충전식 저소음 | 86 | PASS | 3 |
| 10 | 방수 블루투스 스피커 휴대용 IPX7 | 79 | PASS | 3 |
| 11 | 프리미엄 텀블러 보온병 진공 스테인리스 1L | 84 | PASS | 4 |
| 12 | 스마트폰 거치대 차량용 송풍구 마그네틱 | 81 | PASS | 2 |
| 13 | LED 무드등 수면등 침실 터치 조명 | 77 | PASS | 3 |
| 14 | 실리콘 폴더블 물병 접이식 휴대용 | 85 | PASS | 2 |
| 15 | USB 허브 7포트 멀티 고속 충전 | 82 | PASS | 2 |
| 16 | 키보드 마우스 세트 무선 게이밍 | 68 | HOLD | 3 |
| 17 | 멀티탭 USB 충전 개별 스위치 4구 | 87 | PASS | 2 |
| 18 | 무선 충전 패드 고속 15W 스마트폰 | 80 | PASS | 2 |
| 19 | 전동 칫솔 음파 충전식 IPX7 방수 | 76 | PASS | 3 |
| 20 | 전기 포트 무선 주전자 1.7L 자동차단 | 83 | PASS | 2 |

**데이터베이스 위치:** `/home/fortymove/Fortimove-OS/pm-agent/data/approval_queue.db`

---

## 🔄 진행해야 할 검증 단계

### 1단계: 서버 재시작 및 UI 접근 ⏸️

**현재 상황:**
- FastAPI 서버가 실행 중 (health check 정상)
- 하지만 Phase 4 UI routes가 반영되지 않음 (서버 재시작 필요)

**필요 작업:**
```bash
# 서버 재시작
cd /home/fortymove/Fortimove-OS/pm-agent
pkill -f "uvicorn approval_ui_app:app"
source venv/bin/activate
uvicorn approval_ui_app:app --host 0.0.0.0 --port 8000 --reload
```

**접속 URL:**
- Review List: `http://localhost:8000/review/list`
- Review Detail: `http://localhost:8000/review/detail/{review_id}`

### 2단계: 실제 운영자 검수 수행 (10-20개 항목)

**검증 항목:**

#### A. Review List 페이지 테스트
- [ ] 20개 리뷰 항목이 모두 표시되는가?
- [ ] Status 필터 작동 (draft, under_review, approved_for_export, hold, rejected)
- [ ] Search 기능 작동 (상품명, review_id 검색)
- [ ] Stats 표시 정확성 (total, pending, approved count)
- [ ] "Review" 버튼 클릭 시 detail 페이지로 이동

#### B. Review Detail 페이지 테스트
- [ ] Generated content (왼쪽) 읽기 전용 표시
- [ ] Reviewed content (오른쪽) 편집 가능
- [ ] 한글 인코딩 정상 표시 (네이버/쿠팡 제목, 설명, 태그)
- [ ] 이미지 패널 표시 및 interaction
  - [ ] Primary image 설정 (⭐ 뱃지)
  - [ ] 이미지 exclude/restore (❌/✅ 토글)
- [ ] Action 버튼 작동
  - [ ] Save Draft
  - [ ] Hold
  - [ ] Reject
  - [ ] Approve for Export
  - [ ] Export Naver CSV (승인 후)
  - [ ] Export Coupang CSV (승인 후)

#### C. Workflow 테스트
- [ ] draft → under_review 전환
- [ ] under_review → approved_for_export 전환
- [ ] under_review → hold 전환
- [ ] under_review → rejected 전환
- [ ] 잘못된 전환 차단 (예: draft → approved_for_export 직접)

#### D. 데이터 저장 테스트
- [ ] 검수 내용 저장 (Save Draft)
- [ ] review_notes 저장
- [ ] reviewed_* 필드 업데이트 확인
- [ ] review_history 기록 확인

### 3단계: Naver/Coupang CSV Export 테스트

**검증 항목:**

#### A. CSV 파일 생성
- [ ] "Export Naver CSV" 클릭 시 다운로드
- [ ] "Export Coupang CSV" 클릭 시 다운로드
- [ ] 파일명 형식 확인 (예: `naver_export_abc12345.csv`)

#### B. CSV 내용 검증
- [ ] **한글 인코딩**: UTF-8 BOM 또는 EUC-KR 확인
  - Naver/Coupang 업로드 시 인코딩 오류 없는지
- [ ] **헤더 호환성**: Naver/Coupang 요구사항 충족
- [ ] **필드 매핑**: reviewed_* 우선 → generated_* fallback 정확
- [ ] **이미지 URL**: 제외되지 않은 이미지만 포함, primary 우선
- [ ] **가격 형식**: 소수점/통화 형식 정확
- [ ] **태그 형식**: JSON array → comma-separated string 변환

**샘플 CSV 확인 사항:**
```csv
# 예상 헤더 (Naver)
상품명,상품설명,가격,대표이미지,추가이미지1,추가이미지2,태그

# 예상 헤더 (Coupang)
Product Name,Description,Price,Main Image,Additional Images,Tags
```

#### C. Export Log 기록
- [ ] export_log 테이블에 기록 확인
- [ ] export_id, channel, review_ids, exported_by, created_at 확인

### 4단계: 실제 마켓플레이스 업로드 호환성 검증

**필요 작업:**

#### A. Naver 스마트스토어
1. Export Naver CSV 다운로드
2. Naver 스마트스토어 → 상품등록 → 대량등록
3. CSV 파일 업로드
4. 검증 결과 확인:
   - [ ] 업로드 성공
   - [ ] 인코딩 오류 없음
   - [ ] 필드 매핑 정확
   - [ ] 이미지 URL 접근 가능 (현재는 example.com이므로 실패 예상)
   - [ ] 가격/태그 형식 정확

**예상 이슈:**
- 이미지 URL이 example.com이므로 실제 업로드는 실패할 것
- 하지만 **CSV 형식/인코딩/헤더 호환성**은 검증 가능

#### B. Coupang 윙
1. Export Coupang CSV 다운로드
2. Coupang 윙 → 상품등록 → 대량등록
3. CSV 파일 업로드
4. 검증 결과 확인 (동일)

**대안 (이미지 URL 없이 검증):**
- CSV 파일을 Excel/Google Sheets로 열어서 수동 검증
- Naver/Coupang CSV 샘플 템플릿과 비교
- 필드 순서, 인코딩, 형식 일치 여부 확인

### 5단계: 문제점 문서화

**다음 파일에 기록:**
- `/home/fortymove/Fortimove-OS/docs/phase4-validation-findings.md`

**기록할 내용:**

#### A. UI/UX 이슈
- 버튼 클릭 반응 속도
- 한글 입력 시 문제
- 이미지 로딩 속도
- 혼란스러운 UI 요소
- 누락된 안내 메시지

#### B. 인코딩 이슈
- UTF-8 vs EUC-KR 문제
- 특수문자 깨짐
- CSV BOM 필요 여부

#### C. Validation 이슈
- 누락된 검증 로직
- 너무 엄격한 검증
- 에러 메시지 불명확

#### D. API/데이터 이슈
- 느린 응답 시간
- 데이터 누락
- 상태 불일치

#### E. 채널 업로드 이슈
- Naver CSV 헤더 불일치
- Coupang 필드 순서 오류
- 가격/태그 형식 오류

### 6단계: Critical Issue Patching

**발견된 문제 중 Critical만 즉시 수정:**

**Critical 기준:**
- [ ] 운영자가 작업을 완료할 수 없는 blocking 이슈
- [ ] 데이터 손실/손상 가능성
- [ ] CSV 업로드 100% 실패하는 형식 오류
- [ ] 인코딩 오류로 한글 완전 깨짐

**Non-Critical (Phase 5로 이연):**
- UI 개선 (색상, 레이아웃, 애니메이션)
- 편의 기능 (drag-and-drop, bulk actions)
- 성능 최적화 (이미 충분히 빠른 경우)

---

## 🎯 Phase 4 Release Sign-Off 기준

Phase 4가 production-ready로 인정받기 위한 필수 조건:

### Must Have (필수)
- [ ] 운영자가 10-20개 리뷰를 혼란 없이 검수 완료
- [ ] Naver CSV 샘플 업로드 성공 (또는 형식 검증 통과)
- [ ] Coupang CSV 샘플 업로드 성공 (또는 형식 검증 통과)
- [ ] CSV 인코딩 및 헤더 안정성 확인
- [ ] Blocked cases (excluded images, invalid transitions) 정상 차단
- [ ] Critical UI/API/path/static file 이슈 없음

### Nice to Have (선택)
- [ ] 이미지 drag-and-drop reorder
- [ ] Bulk review actions
- [ ] Real-time collaboration locks
- [ ] Advanced search filters

---

## 📊 현재 진행 상황

| 단계 | 작업 | 상태 |
|------|------|------|
| 1 | 샘플 데이터 생성 (20개) | ✅ 완료 |
| 2 | 서버 재시작 및 UI 접근 | ⏸️ 대기 (사용자 수동 작업 필요) |
| 3 | 실제 운영자 검수 (10-20개) | ⏸️ 대기 |
| 4 | Naver/Coupang CSV Export | ⏸️ 대기 |
| 5 | 마켓플레이스 업로드 검증 | ⏸️ 대기 |
| 6 | 문제점 문서화 | ⏸️ 대기 |
| 7 | Critical Issue Patching | ⏸️ 대기 |

---

## 🚀 다음 액션 아이템 (사용자 수동 작업)

### 즉시 수행 (5분):
1. **FastAPI 서버 재시작**
   ```bash
   cd /home/fortymove/Fortimove-OS/pm-agent
   pkill -f "uvicorn approval_ui_app:app"
   source venv/bin/activate
   uvicorn approval_ui_app:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Review Console 접속**
   - 브라우저에서 `http://localhost:8000/review/list` 열기
   - 20개 리뷰 항목이 표시되는지 확인

### 1시간 작업 (운영자 검수):
3. **10-20개 항목 검수 수행**
   - Review list에서 항목 클릭
   - Generated content 확인
   - Reviewed content 편집 (필요 시)
   - 이미지 primary 설정
   - Approve for export

4. **CSV Export 테스트**
   - Approve한 항목에서 "Export Naver CSV" 클릭
   - 다운로드된 CSV 파일 열어보기
   - 인코딩/형식 확인

### 2시간 작업 (마켓플레이스 검증):
5. **Naver/Coupang 업로드 테스트**
   - 실제 Naver 스마트스토어에 CSV 업로드
   - 또는 CSV 템플릿과 수동 비교

6. **문제점 문서화**
   - 발견된 모든 이슈를 `phase4-validation-findings.md`에 기록
   - Critical vs Non-Critical 구분

7. **Critical Issue Patching**
   - Blocking 이슈만 즉시 수정
   - Non-Critical은 Phase 5로 이연

---

## 📝 검증 체크리스트

### UI 기능 검증
- [ ] Review list 페이지 로드
- [ ] Review detail 페이지 로드
- [ ] Generated content 읽기 전용 확인
- [ ] Reviewed content 편집 가능 확인
- [ ] 한글 인코딩 정상 표시
- [ ] 이미지 primary 설정 작동
- [ ] 이미지 exclude 작동
- [ ] Save Draft 작동
- [ ] Hold/Reject/Approve 작동
- [ ] Export CSV 작동

### 데이터 정합성 검증
- [ ] Reviewed_* 값이 저장되는가?
- [ ] Review_history 기록되는가?
- [ ] Export_log 기록되는가?
- [ ] Workflow 전환 히스토리 추적 가능한가?

### CSV Export 검증
- [ ] UTF-8 인코딩 정상
- [ ] 헤더가 Naver/Coupang 요구사항 충족
- [ ] Reviewed_* 우선, generated_* fallback 정확
- [ ] 이미지 URL 제외 로직 정확
- [ ] 가격/태그 형식 정확

### Blocked Path 검증
- [ ] 제외된 이미지만 있을 때 export 차단
- [ ] Draft 상태에서 export 차단
- [ ] Rejected 상태 export 차단
- [ ] 제외된 이미지를 primary로 설정 차단
- [ ] 잘못된 workflow 전환 차단

---

## ⚠️ 알려진 제한사항

1. **이미지 URL이 example.com**
   - 실제 업로드 시 이미지 접근 실패 예상
   - 하지만 CSV 형식/구조 검증은 가능

2. **서버 재시작 필요**
   - Phase 4 UI routes를 서버에 반영하려면 재시작 필수

3. **실제 Naver/Coupang API 연동 없음**
   - CSV 파일 기반 수동 업로드 테스트만 가능

---

**보고일:** 2026-03-31
**다음 업데이트:** 실제 검증 수행 후 `phase4-validation-findings.md` 작성
