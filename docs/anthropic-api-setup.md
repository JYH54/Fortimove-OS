# Anthropic API 설정 가이드

## 1. API 키 모델 접근 권한 부여

### 현재 문제
```
Error code: 404 - {'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-20241022'}}
```
이 에러는 API 키가 해당 모델에 접근할 권한이 없다는 의미입니다.

### 해결 방법

#### A. Anthropic Console에서 확인

1. **Console 접속**
   - https://console.anthropic.com 접속
   - 로그인

2. **API Keys 확인**
   - 좌측 메뉴에서 "API Keys" 클릭
   - 현재 사용 중인 키 확인 (`sk-ant-api03-...` 로 시작)

3. **크레딧 잔액 확인**
   - 좌측 메뉴 "Settings" → "Billing"
   - 크레딧이 0이면 충전 필요

4. **사용 가능한 모델 확인**
   - 좌측 메뉴 "Models" 클릭
   - 다음 모델들이 활성화되어 있는지 확인:
     - `claude-3-5-sonnet-20241022` (최신)
     - `claude-3-5-sonnet-20240620` (이전 버전)
     - `claude-3-opus-20240229`
     - `claude-3-sonnet-20240229`

5. **조직(Organization) 확인**
   - 무료 티어는 일부 모델 접근 제한 가능
   - 좌측 메뉴 "Settings" → "Plans" 에서 플랜 확인

#### B. API로 직접 확인

```bash
# 사용 가능한 모델 목록 확인 (실제로는 Messages API만 제공되지만 테스트 가능)
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": 10,
    "messages": [{"role": "user", "content": "test"}]
  }'
```

**성공 응답 예시**:
```json
{
  "id": "msg_...",
  "type": "message",
  "role": "assistant",
  "content": [{"type": "text", "text": "Test response"}],
  "model": "claude-3-5-sonnet-20241022",
  "stop_reason": "end_turn",
  "usage": {"input_tokens": 10, "output_tokens": 3}
}
```

**실패 응답 (현재 상황)**:
```json
{
  "type": "error",
  "error": {
    "type": "not_found_error",
    "message": "model: claude-3-5-sonnet-20241022"
  }
}
```

#### C. 다른 모델로 변경 시도

현재 API 키로 접근 가능한 모델을 찾기:

```bash
# 다양한 모델 테스트
for model in \
  "claude-3-5-sonnet-20241022" \
  "claude-3-5-sonnet-20240620" \
  "claude-3-opus-20240229" \
  "claude-3-sonnet-20240229" \
  "claude-3-haiku-20240307"
do
  echo "=== Testing: $model ==="
  curl -s https://api.anthropic.com/v1/messages \
    -H "x-api-key: sk-ant-api03-YOUR_API_KEY_HERE" \
    -H "anthropic-version: 2023-06-01" \
    -H "content-type: application/json" \
    -d "{\"model\": \"$model\", \"max_tokens\": 10, \"messages\": [{\"role\": \"user\", \"content\": \"hi\"}]}" \
    | python3 -c "import sys, json; data=json.load(sys.stdin); print('✅ 작동함:', data.get('content', [{}])[0].get('text', '')) if data.get('type') != 'error' else print('❌ 오류:', data.get('error', {}).get('type', ''))"
  echo ""
done
```

### 해결 방법 요약

1. **크레딧 확인**: Console에서 잔액 확인 후 필요시 충전
2. **플랜 확인**: 무료 티어는 일부 모델 제한됨 → 업그레이드 필요
3. **모델 변경**: 코드에서 접근 가능한 모델로 변경
4. **새 API 키 발급**: 필요시 새 키 생성

### 코드에서 모델 변경하는 방법

작동하는 모델을 찾았다면:

**Image Localization 시스템**:
```bash
# .env 파일 수정
nano /home/fortymove/Fortimove-OS/image-localization-system/.env

# TRANSLATION_MODEL 변경
TRANSLATION_MODEL=claude-3-haiku-20240307  # 예시
```

**Daily Wellness Scout**:
```bash
# daily_scout.py 수정
nano /home/fortymove/Fortimove-OS/daily-scout/app/daily_scout.py

# 23번째 줄 수정
self.model = "claude-3-haiku-20240307"  # 또는 작동하는 모델
```

```bash
# 재시작
docker-compose restart backend daily_scout
```

## 2. 일반적인 문제 해결

### 문제 1: 무료 티어 제한
- **증상**: 특정 모델만 404 에러
- **해결**: Paid Plan으로 업그레이드

### 문제 2: 크레딧 소진
- **증상**: 모든 요청이 실패
- **해결**: Console에서 크레딧 충전

### 문제 3: 조직 권한 문제
- **증상**: 다른 계정에서는 작동함
- **해결**: 조직 소유자에게 권한 요청

### 문제 4: 리전 제한
- **증상**: 간헐적 404
- **해결**: 현재는 리전 제한 없음 (US API 엔드포인트만 사용)

## 3. 지원 문의

문제가 지속될 경우:
- Email: support@anthropic.com
- Console: https://console.anthropic.com → "Help" 버튼
- 제공 정보: API 키 앞 4자리, 에러 메시지, request_id
