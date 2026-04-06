# Phase 4 CSV Export Validation Report

**날짜**: 2026-03-31
**검증자**: staging_validator
**서버**: http://localhost:8001 (Port 8001)

---

## 1. 테스트 개요

Phase 4 Review-First Publishing Console의 CSV 내보내기 기능을 실제 데이터로 검증했습니다.

### 테스트 항목
- ✅ 네이버 스마트스토어 CSV 내보내기
- ✅ 쿠팡 Wing CSV 내보내기
- ✅ CSV 파일 인코딩 (UTF-8)
- ✅ 한글 텍스트 표시
- ✅ 이미지 URL 처리

---

## 2. 발견된 주요 이슈 및 수정

### Critical Issue #1: `image_id` KeyError

**문제**:
```
KeyError: 'image_id'
```

- CSV 내보내기 시 `export_service.py` Line 181에서 `img['image_id']` 참조 실패
- 실제 이미지 딕셔너리에 `image_id` 키가 존재하지 않음
- 실제 키: `url`, `order`, `is_primary`, `excluded`, `warnings`

**수정**:
```python
# Before (export_service.py:181)
if img['image_id'] != primary_img['image_id']:

# After
if img.get('url') != primary_img.get('url'):
```

**파일**: [export_service.py:181-182](/home/fortymove/Fortimove-OS/pm-agent/export_service.py#L181-L182)

**결과**: ✅ 수정 후 CSV 내보내기 정상 작동

---

### Critical Issue #2: Workflow State Transition

**문제**:
- `draft` 상태에서 `approved_for_export`로 직접 전환 불가능 (400 Bad Request)
- Phase 4 워크플로우 규칙:
  - `draft` → `[under_review, hold]` (approved_for_export 직행 불가)
  - `under_review` → `[approved_for_export, hold, rejected]`

**해결 방법**:
1. `draft` → `under_review` 먼저 변경
2. `under_review` → `approved_for_export` 변경

**영향**:
- UI에서 "내보내기 승인" 버튼 클릭 시 2단계 전환 필요
- 또는 draft에서 바로 approve 가능하도록 워크플로우 규칙 수정 필요

**상태**: ⚠️ 워크플로우 규칙 재검토 필요 (사용자 경험 개선)

---

## 3. CSV 내보내기 테스트 결과

### Test Case: 키보드 마우스 세트 무선 게이밍
- **Review ID**: `review-ca801831fb5f`
- **상태**: `approved_for_export`
- **테스트 일시**: 2026-03-31 15:25

---

### 3.1 네이버 스마트스토어 CSV

**결과**: ✅ 성공

**출력 파일**: `/tmp/naver_test.csv`

```csv
상품명,판매가,재고수량,상품상세,태그,배송비,반품정보,이미지URL1,이미지URL2,이미지URL3
키보드 마우스 세트 무선 게이밍 RGB 기계식ㅇㅇ,38900.0,100,"프리미엄 게이밍 키보드 마우스 세트

✓ 2.4GHz 무선 안정 연결ㅇㅇㅇㅇㅇ
✓ RGB 백라이트 (16가지)
✓ 기계식 스위치 키감
✓ 6400 DPI 게이밍 마우스",ㅇㅇㅇㅇ,3000,7일 이내 무료 반품,https://example.com/keyboard/main.jpg,https://example.com/keyboard/rgb.jpg,https://example.com/keyboard/mouse.jpg
```

**검증 결과**:
- ✅ 헤더: 네이버 필수 컬럼 포함
- ✅ 한글 인코딩: UTF-8 정상 표시
- ✅ 이미지 URL: 3개 정상 출력 (Primary + 2개 추가)
- ✅ 가격: 38,900원 정상
- ✅ 줄바꿈: 상품상세 내 줄바꿈 정상 처리
- ⚠️ **테스트 데이터 이슈**: "ㅇㅇ", "ㅇㅇㅇㅇㅇ", "ㅇㅇㅇㅇ" 플레이스홀더 텍스트 포함

**파일 크기**: 328 bytes
**파일 인코딩**: `UTF-8 text, with CRLF, LF line terminators`

---

### 3.2 쿠팡 Wing CSV

**결과**: ✅ 성공

**출력 파일**: `/tmp/coupang_test.csv`

```csv
상품명,판매가,할인가,상품설명,태그,배송정보,반품정책,대표이미지
무선 게이밍 키보드 마우스 세트,38900.0,38900.0,"2.4GHz 무선 연결
RGB 백라이트
기계식 스위치
6400 DPI 마우스",,오늘출발 (로켓배송),7일 이내 무료 반품,https://example.com/keyboard/main.jpg
```

**검증 결과**:
- ✅ 헤더: 쿠팡 필수 컬럼 포함
- ✅ 한글 인코딩: UTF-8 정상 표시
- ✅ 이미지 URL: Primary 이미지 1개 출력
- ✅ 가격: 38,900원 정상
- ✅ 할인가: 38,900원 (동일 가격)
- ✅ 배송정보: "오늘출발 (로켓배송)" 기본값
- ⚠️ 태그: 비어있음 (쿠팡 태그 필드 누락)

**파일 크기**: 180 bytes
**파일 인코딩**: `UTF-8 text, with CRLF, LF line terminators`

---

## 4. 기술적 검증 항목

### 4.1 인코딩
- ✅ **UTF-8**: 네이버, 쿠팡 모두 UTF-8 인코딩
- ✅ **한글 정상 표시**: 상품명, 설명, 태그 모두 깨짐 없음
- ⚠️ **BOM 헤더**: UTF-8 BOM 없음 (일부 플랫폼에서 필요할 수 있음)

### 4.2 CSV 형식
- ✅ **Comma 구분자**: 정상
- ✅ **Quote 처리**: 줄바꿈 포함 필드 `"..."`로 정상 감싸짐
- ✅ **CRLF**: Windows 호환 줄바꿈 (`\r\n`)

### 4.3 데이터 매핑
- ✅ `reviewed_*` 필드 우선 사용
- ✅ `generated_*` 필드 Fallback
- ✅ 이미지: `image_review_manager`에서 조회
- ✅ Primary 이미지: `is_primary=true` 우선

---

## 5. 남은 작업 (Staging Validation Checklist)

### 5.1 Critical (P0) - 실제 업로드 전 필수
- [ ] **네이버 실제 업로드 테스트**: 스마트스토어 관리자에서 CSV 업로드 시도
- [ ] **쿠팡 실제 업로드 테스트**: Wing 관리자에서 CSV 업로드 시도
- [ ] **UTF-8 BOM 추가 필요 여부**: 플랫폼별 요구사항 확인
- [ ] **워크플로우 UX 개선**: draft → approved_for_export 직접 전환 지원 또는 UI에서 2단계 자동 처리

### 5.2 Major (P1) - 배포 전 권장
- [ ] **테스트 데이터 정리**: "ㅇㅇㅇ" 플레이스홀더 제거
- [ ] **쿠팡 태그 필드**: 태그가 비어있는 이유 확인 및 수정
- [ ] **필드 검증**: 각 플랫폼 필수 필드 누락 여부 재확인
- [ ] **대용량 CSV**: 10개, 50개, 100개 상품 동시 내보내기 테스트

### 5.3 Minor (P2) - 선택적 개선
- [ ] **이미지 순서**: 쿠팡도 여러 이미지 지원 여부 확인
- [ ] **가격 포맷**: 소수점 vs 정수 (38900.0 → 38900)
- [ ] **배송비 동적 계산**: 하드코딩 3000원 → 실제 계산 로직

---

## 6. API 호출 예시

### 네이버 CSV 내보내기
```bash
curl -X POST "http://localhost:8001/api/phase4/review/export/csv" \
  -H "Content-Type: application/json" \
  -d '{
    "review_ids": ["review-ca801831fb5f"],
    "channel": "naver",
    "exported_by": "staging_validator"
  }'
```

### 쿠팡 CSV 내보내기
```bash
curl -X POST "http://localhost:8001/api/phase4/review/export/csv" \
  -H "Content-Type: application/json" \
  -d '{
    "review_ids": ["review-ca801831fb5f"],
    "channel": "coupang",
    "exported_by": "staging_validator"
  }'
```

---

## 7. 결론

### ✅ 검증 통과 항목
1. CSV 내보내기 기본 기능 정상 작동
2. UTF-8 한글 인코딩 정상
3. 이미지 URL 매핑 정상
4. 네이버/쿠팡 CSV 헤더 정상
5. 줄바꿈, Quote 처리 정상

### ⚠️ 해결된 Critical Issue
1. **image_id KeyError** → URL 비교로 수정 완료
2. **Workflow State Transition** → 2단계 전환으로 우회 (UX 개선 필요)

### 🔴 남은 Critical Task
1. **실제 플랫폼 업로드 테스트** (네이버, 쿠팡)
2. **CSV 인코딩 호환성** (UTF-8 BOM 필요 여부)
3. **Workflow UX 개선** (draft → approved_for_export 직접 전환)

---

**다음 단계**: 실제 네이버 스마트스토어 및 쿠팡 Wing 관리자에서 CSV 업로드 테스트를 진행하여 필드 매핑, 인코딩, 포맷 호환성을 최종 검증합니다.
