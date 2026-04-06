# Phase 4 Staging Validation Findings

**검증일:** 2026-03-31
**검증자:** 실제 운영자 (사용자)
**환경:** localhost:8001

---

## 📊 검증 요약

### 테스트 범위
- ✅ Review List 페이지 접속
- ✅ 26개 리뷰 항목 로드 확인
- ✅ Review Detail 페이지 접속
- ✅ Status 필터 테스트
- ⚠️ CSV Export 테스트 (작동 안 함)

### 발견된 문제점
- **Critical:** 3개
- **Major:** 1개
- **Minor:** 2개

---

## 🔴 Critical Issues (Blocking, 즉시 수정 필요)

### 1. Review Detail 페이지: Generated Content 데이터 로드 안 됨

**문제:**
- Generated Content (READ-ONLY) 섹션이 모두 빈 값 ("-")으로 표시
- Naver Title, Naver Description, Coupang Title, Price 등 모두 비어있음
- 데이터베이스에는 `generated_naver_title` 등의 값이 있지만 UI에 표시되지 않음

**스크린샷 증거:**
- 왼쪽 "Generated Content (READ-ONLY)" 패널의 모든 필드가 "-"

**영향:**
- 운영자가 AI 생성 결과물을 볼 수 없음
- 검수 작업 불가능 (비교 대상이 없음)
- **Blocking Issue**

**원인 추정:**
- API가 `generated_*` 필드를 반환하지 않음
- 또는 JavaScript가 올바른 필드명을 참조하지 않음

**우선순위:** P0 (최우선)

---

### 2. CSV Export 버튼 작동 안 함

**문제:**
- Review Detail 페이지의 "Export Naver CSV", "Export Coupang CSV" 버튼이 작동하지 않음
- 또는 버튼이 비활성화되어 있음 (승인 전이어서일 수 있음)

**스크린샷 증거:**
- Actions 섹션이 잘림 (하단 스크롤 필요할 수 있음)

**영향:**
- CSV 내보내기 테스트 불가능
- 마켓플레이스 업로드 호환성 검증 불가
- **Blocking Issue**

**확인 필요:**
- 버튼이 아예 없는지, 비활성화된 것인지
- Approve for Export 후 활성화되는지

**우선순위:** P0 (최우선)

---

### 3. Review List 한글 번역 미흡

**문제:**
- 테이블 헤더가 영어로 되어 있음:
  - "Review ID", "Product Title", "Score", "Decision", "Status", "Primary Image", "Export Ready", "Updated", "Actions"
- 한국 운영자를 위한 서비스인데 영어 UI는 혼란 유발

**스크린샷 증거:**
- Review List 테이블 헤더 모두 영어

**영향:**
- 운영자 UX 저하
- 헤더 의미 파악에 시간 소요
- **Major Usability Issue**

**권장 한글 번역:**
- Review ID → 리뷰 ID
- Product Title → 상품명
- Score → 점수
- Decision → 판정
- Status → 상태
- Primary Image → 대표 이미지
- Export Ready → 내보내기 가능
- Updated → 수정일
- Actions → 작업

**우선순위:** P1 (높음)

---

## ⚠️ Major Issues (중요, 빠른 수정 권장)

### 4. Status 필터 "Hold" 선택 시 "No reviews found"

**문제:**
- Status Filter를 "Hold"로 선택하면 "No reviews found" 메시지
- 그러나 생성한 샘플 데이터 중 HOLD decision 항목이 3개 있음:
  - 전기 그릴 (Score: 75, HOLD)
  - 스마트 체중계 (Score: 72, HOLD)
  - 키보드 마우스 세트 (Score: 68, HOLD)

**스크린샷 증거:**
- Status Filter = "Hold" 선택 시 빈 테이블

**영향:**
- HOLD 상태 항목을 필터링할 수 없음
- 운영자가 보류된 항목을 관리하기 어려움

**원인 추정:**
- `decision` 컬럼과 `review_status` 컬럼을 혼동
- `decision = "HOLD"` vs `review_status = "hold"` 차이
- 필터가 `review_status`를 보는데, 우리 샘플 데이터는 `decision = "HOLD"`로 설정했고 `review_status = "draft"`

**해결 방법:**
- Status 필터는 `review_status` 컬럼을 필터링해야 함
- HOLD decision은 별도 필터 필요하거나, workflow에서 HOLD 상태로 전환해야 함

**우선순위:** P1 (높음)

---

## 📝 Minor Issues (사소함, 나중에 수정 가능)

### 5. Primary Image 컬럼에 "?" 표시

**문제:**
- Primary Image 컬럼에 모든 항목이 "?" (물음표)로 표시

**영향:**
- 대표 이미지 설정 여부를 한눈에 파악 불가
- 하지만 Review Detail에서는 확인 가능하므로 blocking은 아님

**원인:**
- API가 primary image 존재 여부를 반환하지 않음
- 또는 JavaScript가 올바른 필드를 참조하지 않음

**우선순위:** P2 (낮음)

---

### 6. Export Ready 컬럼에 "✗" 표시

**문제:**
- Export Ready 컬럼에 모든 항목이 "✗" (X 표시)

**영향:**
- 내보내기 가능 여부를 한눈에 파악 불가
- 하지만 status가 "draft"이므로 정상적으로 ✗인 것일 수 있음

**확인 필요:**
- Approve for Export 후 ✓로 변경되는지

**우선순위:** P2 (낮음)

---

## ✅ 정상 작동 확인된 기능

1. **Review List 로드** - 26개 항목 모두 표시
2. **한글 상품명 표시** - 인코딩 문제 없음
3. **Score 표시** - 색상 구분 (빨강/주황/초록)
4. **Decision 표시** - 뱃지 스타일 (PASS/HOLD)
5. **Status 표시** - "draft" 뱃지
6. **Review 버튼** - Detail 페이지 이동 정상
7. **Back to List 버튼** - List 페이지로 돌아가기 정상
8. **Reviewed Content 편집** - 입력 필드 모두 편집 가능
9. **Image Review Panel** - 이미지 3개 표시, PRIMARY 뱃지, exclude 버튼 표시
10. **Actions 버튼** - Save Draft, Hold, Reject, Approve for Export 버튼 표시

---

## 🔧 즉시 수정해야 할 Critical Issues

### Priority Order:

1. **P0-1: Review Detail Generated Content 로드 안 됨**
   - 파일: `review_console_api.py`, `review_detail.js`
   - 수정: API가 `generated_*` 필드를 올바르게 반환하도록
   - 수정: JavaScript가 올바른 필드명으로 데이터 표시하도록

2. **P0-2: CSV Export 버튼 작동 확인 및 수정**
   - 파일: `review_detail.js`, `export_service.py`
   - 확인: Approve for Export 후 버튼 활성화되는지
   - 수정: CSV export API 호출 및 다운로드 로직

3. **P1-1: Review List 한글 번역**
   - 파일: `review_list.html`
   - 수정: 테이블 헤더를 한글로 변경

4. **P1-2: Status 필터 "Hold" 작동**
   - 파일: 샘플 데이터 또는 필터 로직
   - 수정: HOLD decision을 가진 항목을 "hold" review_status로 설정
   - 또는: Decision 필터를 별도로 추가

---

## 📊 추가 검증 필요

1. **Workflow 전환 테스트**
   - [ ] draft → under_review
   - [ ] under_review → approved_for_export
   - [ ] approved_for_export → CSV Export 가능 확인

2. **Save Draft 기능**
   - [ ] Reviewed content 수정 후 저장
   - [ ] 새로고침 후 수정 내용 유지 확인

3. **Image Review 기능**
   - [ ] Primary 이미지 변경
   - [ ] 이미지 exclude/restore
   - [ ] Excluded image를 primary로 설정 차단 확인

4. **CSV Export 전체 플로우**
   - [ ] Approve for Export
   - [ ] Export Naver CSV 다운로드
   - [ ] Export Coupang CSV 다운로드
   - [ ] CSV 파일 인코딩 확인 (UTF-8 BOM)
   - [ ] CSV 헤더 확인
   - [ ] Reviewed_* vs Generated_* 우선순위 확인

---

## 🎯 다음 단계

1. ✅ 발견 사항 문서화 (이 파일)
2. ⏭️ Critical Issues P0-1, P0-2, P1-1 즉시 수정
3. ⏭️ 수정 후 재검증
4. ⏭️ CSV Export 전체 플로우 테스트
5. ⏭️ Naver/Coupang 마켓플레이스 업로드 호환성 검증

---

**문서 작성:** 2026-03-31
**다음 업데이트:** Critical Issues 수정 후
