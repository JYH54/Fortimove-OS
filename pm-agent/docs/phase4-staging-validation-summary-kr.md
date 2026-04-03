# Phase 4 Staging Validation 중간 보고서

**검증 날짜**: 2026-03-31
**검증 서버**: localhost:8001
**검증자**: Claude (Staging Validator)

---

## 📋 검증 요약

Phase 4 Review-First Publishing Console의 **한글 UI 및 CSV 내보내기 기능**을 실제 데이터로 검증했습니다.

### 주요 성과
- ✅ **한글 UI 번역 완료**: 리뷰 목록, 상세 페이지 주요 텍스트 한글화
- ✅ **네이버 CSV 내보내기 작동**: UTF-8, 한글 정상, 이미지 3개 출력
- ✅ **쿠팡 CSV 내보내기 작동**: UTF-8, 한글 정상, Primary 이미지 출력
- ✅ **Critical Bug 수정**: `image_id` KeyError 해결

### 발견된 문제
- 🔴 **Workflow UX 이슈**: draft → approved_for_export 직접 전환 불가 (2단계 필요)
- ⚠️ **실제 업로드 미검증**: 네이버/쿠팡 플랫폼 실제 업로드 테스트 필요
- ⚠️ **테스트 데이터 품질**: "ㅇㅇㅇ" 플레이스홀더 포함

---

## 1. 한글 UI 구현 현황

### 1.1 리뷰 목록 페이지 (`/review/list`)

**변경 사항**:

| 항목 | Before | After |
|------|--------|-------|
| 테이블 헤더 | Review ID, Product Title, Score, Decision, Status | 리뷰 ID, 상품명, 점수, 판정, 상태 |
| 필터 | Status Filter, Search, All | 상태 필터, 검색, 전체 |
| 상태 옵션 | Draft, Under Review, Approved for Export, Hold, Rejected | 초안, 검수 중, 내보내기 승인, 보류, 거부 |
| 통계 | Total, Pending, Approved | 전체, 대기 중, 승인됨 |
| 버튼 | Refresh | 새로고침 |

**파일**: [templates/review_list.html](/home/fortymove/Fortimove-OS/pm-agent/templates/review_list.html)

**검증 결과**: ✅ 한글 정상 표시 (사용자 스크린샷으로 확인됨)

---

### 1.2 리뷰 상세 페이지 (`/review/detail/{review_id}`)

**변경 사항**:

| 섹션 | Before | After |
|------|--------|-------|
| 네비게이션 | ← Back to List | ← 목록으로 돌아가기 |
| 자동 생성 콘텐츠 | Generated Content (READ-ONLY) | 자동 생성 콘텐츠 (읽기 전용) |
| 검수 콘텐츠 | Reviewed Content (EDITABLE) | 검수 콘텐츠 (편집 가능) |
| 이미지 검수 | Image Review | 이미지 검수 |
| 작업 섹션 | Actions, Review Status | 작업, 검수 상태 |
| 버튼 | Save Draft, Hold, Reject, Approve for Export | 초안 저장, 보류, 거부, 내보내기 승인 |
| CSV 버튼 | Export Naver CSV, Export Coupang CSV | 네이버 CSV 내보내기, 쿠팡 CSV 내보내기 |

**파일**: [templates/review_detail.html](/home/fortymove/Fortimove-OS/pm-agent/templates/review_detail.html)

**검증 결과**: ✅ 한글 정상 표시

---

## 2. CSV 내보내기 기능 검증

### 2.1 Critical Bug 수정: `image_id` KeyError

**문제**:
```
KeyError: 'image_id'
File: export_service.py, Line: 181
```

**원인**:
- `image_review` 테이블에서 가져온 이미지 딕셔너리에 `image_id` 키 없음
- 실제 키: `url`, `order`, `is_primary`, `excluded`, `warnings`
- 코드는 `img['image_id']` 참조 시도 → KeyError 발생

**수정**:
```python
# Before
if img['image_id'] != primary_img['image_id']:

# After
if img.get('url') != primary_img.get('url'):
```

**수정 파일**: [export_service.py:181-182](/home/fortymove/Fortimove-OS/pm-agent/export_service.py#L181-L182)

**결과**: ✅ CSV 내보내기 정상 작동

---

### 2.2 네이버 CSV 내보내기

**테스트 케이스**:
- Review ID: `review-ca801831fb5f`
- 상품: 키보드 마우스 세트 무선 게이밍
- 가격: 38,900원

**출력 결과**:
```csv
상품명,판매가,재고수량,상품상세,태그,배송비,반품정보,이미지URL1,이미지URL2,이미지URL3
키보드 마우스 세트 무선 게이밍 RGB 기계식ㅇㅇ,38900.0,100,"프리미엄 게이밍 키보드 마우스 세트..."
```

**검증 결과**:
- ✅ 헤더: 네이버 필수 컬럼 포함
- ✅ 인코딩: UTF-8, 한글 정상 표시
- ✅ 이미지: 3개 (Primary + 2개 추가)
- ✅ 가격: 38,900원
- ✅ 줄바꿈: CSV Quote 처리 정상
- ⚠️ 테스트 데이터: "ㅇㅇ", "ㅇㅇㅇㅇ" 플레이스홀더 포함

**파일 크기**: 328 bytes
**파일 정보**: `UTF-8 text, with CRLF, LF line terminators`

---

### 2.3 쿠팡 CSV 내보내기

**출력 결과**:
```csv
상품명,판매가,할인가,상품설명,태그,배송정보,반품정책,대표이미지
무선 게이밍 키보드 마우스 세트,38900.0,38900.0,"2.4GHz 무선 연결..."
```

**검증 결과**:
- ✅ 헤더: 쿠팡 필수 컬럼 포함
- ✅ 인코딩: UTF-8, 한글 정상 표시
- ✅ 이미지: Primary 이미지 1개
- ✅ 가격: 38,900원
- ⚠️ 태그: 비어있음

**파일 크기**: 180 bytes
**파일 정보**: `UTF-8 text, with CRLF, LF line terminators`

---

## 3. 발견된 문제 및 개선 사항

### 3.1 Critical (P0) - 배포 전 필수 해결

#### 🔴 Issue #1: Workflow State Transition UX

**문제**:
- "내보내기 승인" 버튼 클릭 시 400 Bad Request 발생
- `draft` 상태에서 `approved_for_export`로 직접 전환 불가능

**원인**:
Phase 4 워크플로우 규칙 ([review_workflow.py](/home/fortymove/Fortimove-OS/pm-agent/review_workflow.py))
```python
'draft': {
    'allowed_next_states': ['under_review', 'hold']
}
'under_review': {
    'allowed_next_states': ['approved_for_export', 'hold', 'rejected']
}
```

**현재 해결책**:
1. `draft` → `under_review` 먼저 변경
2. `under_review` → `approved_for_export` 변경

**권장 개선 방안**:
- **옵션 A**: 워크플로우 규칙 수정 (draft → approved_for_export 직접 허용)
- **옵션 B**: UI에서 자동 2단계 전환 (JavaScript에서 처리)
- **옵션 C**: "빠른 승인" 버튼 추가 (draft → under_review → approved_for_export 자동)

**우선순위**: 🔴 P0 (사용자 혼란 방지)

---

#### 🔴 Issue #2: 실제 플랫폼 업로드 미검증

**문제**:
- 네이버 스마트스토어 실제 CSV 업로드 테스트 안 함
- 쿠팡 Wing 실제 CSV 업로드 테스트 안 함

**위험**:
- 필드 이름 불일치
- 인코딩 호환성 (UTF-8 BOM 필요 여부)
- 필수 필드 누락
- 데이터 포맷 오류

**다음 단계**:
1. 네이버 스마트스토어 판매자 센터 접속
2. 상품 일괄 등록 → CSV 업로드 시도
3. 쿠팡 Wing 판매자 센터 접속
4. 상품 일괄 등록 → CSV 업로드 시도
5. 오류 발생 시 필드 매핑 수정

**우선순위**: 🔴 P0 (배포 전 필수)

---

### 3.2 Major (P1) - 배포 전 권장

#### ⚠️ Issue #3: 테스트 데이터 품질

**문제**:
- 샘플 데이터에 "ㅇㅇ", "ㅇㅇㅇㅇㅇ" 플레이스홀더 포함
- 실제 운영 검증 시 혼란 야기 가능

**예시**:
```
키보드 마우스 세트 무선 게이밍 RGB 기계식ㅇㅇ  # "ㅇㅇ" 불필요
✓ 2.4GHz 무선 안정 연결ㅇㅇㅇㅇㅇ  # "ㅇㅇㅇㅇㅇ" 불필요
```

**해결 방안**:
- 테스트 데이터 재생성 (플레이스홀더 제거)
- 또는 실제 상품 데이터로 교체

**우선순위**: ⚠️ P1

---

#### ⚠️ Issue #4: 쿠팡 태그 필드 비어있음

**문제**:
- 쿠팡 CSV에서 태그 필드가 비어있음
- 네이버 CSV에는 태그 포함됨

**원인 추정**:
- `reviewed_coupang_tags` 또는 `generated_coupang_tags` 필드 없음
- 또는 매핑 로직 누락

**다음 단계**:
- `export_service.py`에서 쿠팡 태그 매핑 확인
- 필요 시 태그 필드 추가

**우선순위**: ⚠️ P1

---

### 3.3 Minor (P2) - 선택적 개선

- [ ] 가격 소수점 제거 (38900.0 → 38900)
- [ ] 배송비 동적 계산 (하드코딩 3000원 제거)
- [ ] 대용량 CSV 테스트 (100개 상품)
- [ ] UI 필드 레이블 추가 한글화 (Naver Title → 네이버 제목 등)

---

## 4. 기술적 검증 결과

### 4.1 인코딩
- ✅ UTF-8 인코딩 정상
- ✅ 한글 텍스트 깨짐 없음
- ⚠️ UTF-8 BOM 미포함 (일부 플랫폼에서 필요할 수 있음)

### 4.2 CSV 형식
- ✅ Comma 구분자
- ✅ Quote 처리 (줄바꿈 포함 필드)
- ✅ CRLF 줄바꿈 (Windows 호환)

### 4.3 데이터 매핑
- ✅ `reviewed_*` 필드 우선 사용
- ✅ `generated_*` 필드 Fallback
- ✅ 이미지 URL 정상 추출

---

## 5. 다음 단계 (우선순위순)

### 🔴 P0 (Critical) - 즉시 처리 필요

1. **실제 플랫폼 업로드 테스트**
   - [ ] 네이버 스마트스토어 CSV 업로드 시도
   - [ ] 쿠팡 Wing CSV 업로드 시도
   - [ ] 오류 발생 시 필드 매핑 수정

2. **Workflow UX 개선**
   - [ ] draft → approved_for_export 직접 전환 지원
   - [ ] 또는 UI에서 자동 2단계 전환 구현

### ⚠️ P1 (Major) - 배포 전 권장

3. **데이터 품질 개선**
   - [ ] 테스트 데이터 정리 ("ㅇㅇㅇ" 제거)
   - [ ] 실제 상품 데이터로 20개 샘플 재생성

4. **쿠팡 태그 필드 수정**
   - [ ] 태그 매핑 로직 확인 및 수정

### 📝 P2 (Minor) - 선택적 개선

5. **UI 세부 개선**
   - [ ] 필드 레이블 추가 한글화
   - [ ] 가격 포맷 정수로 변경

6. **성능 테스트**
   - [ ] 100개 상품 동시 내보내기 테스트

---

## 6. Phase 4 Release Sign-off 체크리스트

사용자가 제시한 성공 기준 검증:

| 항목 | 상태 | 비고 |
|------|------|------|
| 운영자가 혼란 없이 검수 및 내보내기 가능 | ⚠️ | Workflow UX 개선 필요 |
| 네이버 샘플 업로드 성공 | 🔴 | 미검증 (P0) |
| 쿠팡 샘플 업로드 성공 | 🔴 | 미검증 (P0) |
| CSV 인코딩 및 헤더 안정 | ✅ | UTF-8 정상 |
| 블로킹 케이스 정상 차단 | ⏸️ | 추가 테스트 필요 |
| Critical UI/API/경로 이슈 없음 | ✅ | image_id KeyError 해결 |

**현재 상태**: ⚠️ **개발 완료, Release Sign-off 보류**

**보류 사유**:
1. 실제 플랫폼 업로드 검증 필요
2. Workflow UX 개선 필요

---

## 7. 결론

### ✅ 성공한 항목
1. 한글 UI 번역 완료
2. CSV 내보내기 기본 기능 작동
3. UTF-8 인코딩 정상
4. Critical Bug (image_id KeyError) 수정

### 🔴 남은 Critical Task
1. **실제 플랫폼 CSV 업로드 테스트**
2. **Workflow UX 개선** (draft → approved_for_export 직접 전환)

### 📊 전체 진행률
- **한글화**: 90% 완료 (주요 UI 완료, 세부 레이블 남음)
- **CSV 내보내기**: 70% 완료 (기능 작동, 실제 업로드 미검증)
- **Workflow**: 80% 완료 (기능 정상, UX 개선 필요)

---

**최종 권장 사항**:
1. 실제 네이버/쿠팡 플랫폼에서 CSV 업로드 테스트 진행
2. 테스트 결과에 따라 필드 매핑 및 인코딩 수정
3. Workflow UX 개선 후 Phase 4 Release Sign-off

**담당자**: 사용자 (실제 플랫폼 계정 필요)
**예상 소요 시간**: 1-2시간 (플랫폼 접근 가능 시)
