# API 키 진단 결과

## 테스트 결과

모든 Claude 모델에서 404 `not_found_error` 발생:

- ❌ `claude-3-5-sonnet-20250219`
- ❌ `claude-3-5-sonnet-20241022`
- ❌ `claude-3-5-sonnet-20240620`
- ❌ `claude-3-opus-20240229`
- ❌ `claude-3-sonnet-20240229`
- ❌ `claude-3-haiku-20240307`

## 문제 원인

API 키 `sk-ant-api03-REDACTED`가 **어떤 모델에도 접근 권한이 없는 상태**입니다.

### 가능한 원인:

1. **무료 체험 계정**: 크레딧이 소진되었거나 모델 접근이 제한된 계정
2. **조직 권한 문제**: API 키가 속한 조직에서 모델 사용이 비활성화됨
3. **API 키 제한**: 특정 용도로만 제한된 키 (예: 내부 테스트용)
4. **결제 문제**: 크레딧 잔액이 0이거나 결제 수단 미등록

## 해결 방법

### 1. Anthropic Console 확인 (가장 중요!)

https://console.anthropic.com 에 로그인하여:

#### A. 크레딧 잔액 확인
```
Settings → Billing → Credits
```
- 잔액이 $0.00이면 → **크레딧 충전 필요**
- "Add Credits" 버튼으로 최소 $5 충전

#### B. API 키 상태 확인
```
Settings → API Keys
```
- 현재 키가 목록에 있는지 확인
- "Status" 열에서 활성화 상태 확인
- 비활성화되어 있다면 → **재활성화 또는 새 키 발급**

#### C. 플랜 확인
```
Settings → Plans
```
- 현재 플랜: Free / Build / Scale / Enterprise
- **Free 플랜**은 일부 모델 제한 가능 → **Build 플랜으로 업그레이드** ($5/month)

#### D. 조직 권한 확인
```
Settings → Organization
```
- "Members" 탭에서 본인 권한 확인
- "Admin" 또는 "Developer" 권한 필요
- "Viewer"는 API 사용 불가

### 2. 새 API 키 발급

현재 키가 작동하지 않으면 새로 발급:

1. Console → Settings → API Keys
2. "Create Key" 클릭
3. Name: "Fortimove Production"
4. 생성된 키 복사 (한 번만 표시됨!)

```bash
# .env 파일 업데이트
nano /home/fortymove/Fortimove-OS/image-localization-system/.env

# ANTHROPIC_API_KEY 변경
ANTHROPIC_API_KEY=sk-ant-api03-...새로운키...

# 재시작
docker-compose restart backend daily_scout
```

### 3. 결제 수단 등록

Console → Settings → Billing → Payment Methods

- 신용카드 등록 필요 (자동 충전 설정 가능)
- 최소 충전 금액: $5
- 사용량 기준 과금

### 4. 대안: 무료 체험 신청

Anthropic에서 무료 크레딧 받기:

- 이메일: sales@anthropic.com
- 제목: "Free Trial Request for Fortimove Project"
- 내용: 프로젝트 설명 + 예상 사용량

일반적으로 $10-50 무료 크레딧 제공

## 임시 해결책 (테스트용)

API 접근 문제 해결 전까지 시스템을 Mock 모드로 실행:

### daily_scout.py 수정

`/home/fortymove/Fortimove-OS/daily-scout/app/daily_scout.py` 파일의 95번째 줄 근처에 Mock 함수 추가:

```python
async def scan_region(self, region_code: str, config: Dict) -> List[Dict]:
    """특정 지역의 웰니스 트렌드 스캔"""

    # ============= MOCK 모드 (API 접근 불가 시) =============
    # TODO: API 정상화 후 이 섹션 삭제
    logger.warning(f"⚠️ MOCK 모드: {region_code} 샘플 데이터 반환")
    return [
        {
            "product_name": f"[MOCK] {region_code} 샘플 상품 1",
            "brand": "Sample Brand",
            "price": "$19.99",
            "category": "프로바이오틱스",
            "source": config["platforms"][0],
            "trend_score": 75,
            "korea_demand": "중간",
            "description": "테스트용 샘플 데이터입니다.",
            "url": "https://example.com"
        }
    ]
    # ============= MOCK 모드 끝 =============

    # 아래 원래 코드는 주석 처리
    # try:
    #     response = self.client.messages.create(
    #         ...
```

이렇게 하면 API 없이도 시스템 전체 흐름을 테스트할 수 있습니다.

## 비용 참고

### Claude API 가격 (2026년 기준)

| 모델 | Input (1M tokens) | Output (1M tokens) |
|------|-------------------|-------------------|
| Claude 3.5 Sonnet | $3.00 | $15.00 |
| Claude 3 Opus | $15.00 | $75.00 |
| Claude 3 Haiku | $0.25 | $1.25 |

### 예상 비용 (Daily Scout)

- 하루 4개 지역 스캔
- 각 스캔당 ~2,000 tokens (input) + ~5,000 tokens (output)
- 하루 총: 8,000 input + 20,000 output tokens

**일일 비용 (Sonnet 기준)**:
- Input: 0.008M × $3 = $0.024
- Output: 0.02M × $15 = $0.30
- **합계: ~$0.32/일 ≈ $10/월**

**권장**: Claude 3 Haiku로 변경하면 **$0.03/일 ≈ $1/월**

## 연락처

Anthropic 지원팀:
- Email: support@anthropic.com
- Console: https://console.anthropic.com (Help 버튼)
- 응답 시간: 24-48시간

문의 시 포함할 정보:
- API 키 앞 10자리: `sk-ant-api03--15LCuuUd2O...`
- 에러 메시지: `not_found_error`
- 사용 목적: "E-commerce product analysis"
