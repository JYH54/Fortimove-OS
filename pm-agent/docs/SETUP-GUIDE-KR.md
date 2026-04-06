# PM Agent 시스템 설정 가이드

**목적**: Product Content Pack 생성 시스템 시작 전 필수 설정

---

## 🚀 Quick Start (5분)

### Step 1: ANTHROPIC_API_KEY 설정 (필수)

모든 AI 에이전트가 작동하려면 Anthropic API 키가 필요합니다.

#### 1.1 API 키 발급

1. https://console.anthropic.com/ 접속
2. API Keys 메뉴 선택
3. "Create Key" 클릭
4. 키 복사 (sk-ant-api03-로 시작)

#### 1.2 .env 파일 생성

```bash
# pm-agent 디렉토리로 이동
cd /home/fortymove/Fortimove-OS/pm-agent

# .env 파일 생성
cp .env.template .env

# API 키 입력 (vi 또는 nano 사용)
nano .env
```

**.env 파일 편집**:
```bash
# 이 줄을 찾아서
ANTHROPIC_API_KEY=your-api-key-here

# 실제 API 키로 교체
ANTHROPIC_API_KEY=sk-ant-api03-REDACTED...
```

저장: `Ctrl+O` → `Enter` → `Ctrl+X`

---

### Step 2: 서버 재시작

```bash
# 기존 서버 종료
pkill -f "uvicorn approval_ui_app"

# 새 서버 시작
cd /home/fortymove/Fortimove-OS/pm-agent
python3 -m uvicorn approval_ui_app:app --host 127.0.0.1 --port 8001 --reload
```

---

### Step 3: 설정 확인

```bash
# Health check
curl -s http://localhost:8001/health | python3 -m json.tool

# Agent 상태 확인
curl -s http://localhost:8001/api/agents/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
for name, data in sorted(d.get('agents', {}).items()):
    print(f'{name}: {data.get(\"status\", \"unknown\")}')
"
```

**예상 출력**:
```
cs: idle
pm: idle
pricing: idle
product_registration: idle
sourcing: idle
```

---

## 🔧 Advanced Setup (선택 사항)

### Korean Law MCP 연동 (법률 검토 기능)

```bash
# .env 파일에 추가
LAW_OC=dydgh5942zy
```

### Slack 알림 설정

```bash
# Slack Webhook URL 발급
# https://api.slack.com/messaging/webhooks

# .env 파일에 추가
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Email 알림 설정

```bash
# .env 파일에 추가
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_FROM=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
```

---

## 🧪 테스트

### Test 1: Sourcing Agent 실행

```bash
curl -s -X POST http://localhost:8001/api/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "sourcing",
    "input": {
      "source_url": "https://item.taobao.com/item.htm?id=123456",
      "source_title": "스테인리스 텀블러",
      "market": "korea",
      "source_price_cny": 30.0,
      "weight_kg": 0.5
    },
    "save_to_queue": false
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Status: {d.get(\"status\")}')
print(f'Result: {d.get(\"result\", {})}')
"
```

**예상 출력**:
```
Status: completed
Result: {'decision': 'PASS', 'score': 75, ...}
```

---

### Test 2: Content Agent 실행

```bash
curl -s -X POST http://localhost:8001/api/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent": "content",
    "input": {
      "product_name": "스테인리스 텀블러",
      "product_category": "주방용품",
      "key_features": ["진공 단열", "500ml", "휴대용"],
      "price": 15900,
      "content_type": "product_page",
      "compliance_mode": true
    },
    "save_to_queue": false
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
result = d.get('result', {})
print(f'Status: {d.get(\"status\")}')
print(f'Naver Title: {result.get(\"naver_title\", \"N/A\")[:50]}...')
"
```

---

## 📊 Product Content Pack 스키마 추가

### Step 4: Database Schema 확장

```bash
cd /home/fortymove/Fortimove-OS/pm-agent

python3 << 'EOF'
import sqlite3
from pathlib import Path

db_path = Path('data/approval_queue.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add Product Content Pack fields
fields = [
    ('generated_detail_page_plan', 'TEXT'),
    ('reviewed_detail_page_plan', 'TEXT'),
    ('generated_product_info_json', 'TEXT'),
    ('reviewed_product_info_json', 'TEXT'),
    ('generated_promotion_strategy_json', 'TEXT'),
    ('reviewed_promotion_strategy_json', 'TEXT'),
]

for field_name, field_type in fields:
    try:
        cursor.execute(f'''
            ALTER TABLE approval_queue
            ADD COLUMN {field_name} {field_type}
        ''')
        print(f'✅ Added: {field_name}')
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e):
            print(f'⏭️ Skip: {field_name} (already exists)')
        else:
            print(f'❌ Error: {field_name} - {e}')

conn.commit()

# Verify
cursor.execute('PRAGMA table_info(approval_queue)')
columns = cursor.fetchall()
new_cols = [c[1] for c in columns if 'detail_page' in c[1] or 'product_info' in c[1] or 'promotion' in c[1]]

print(f'\n📊 Product Content Pack Fields ({len(new_cols)}/6):')
for col in new_cols:
    print(f'  • {col}')

conn.close()
EOF
```

---

## 🎯 다음 단계

설정 완료 후:

1. **Content Agent 확장** - 상세 페이지, 프로모션 전략 생성 기능 추가
2. **UI 재설계** - Product Content Pack 편집 UI
3. **Workflow 조정** - Export를 선택 사항으로 변경

---

## ❓ Troubleshooting

### 문제: "Content Agent initiated without ANTHROPIC_API_KEY"

**해결**:
```bash
# .env 파일 확인
cat /home/fortymove/Fortimove-OS/pm-agent/.env | grep ANTHROPIC

# API 키가 없으면 추가
echo 'ANTHROPIC_API_KEY=sk-ant-api03-...' >> .env

# 서버 재시작
pkill -f uvicorn
python3 -m uvicorn approval_ui_app:app --host 127.0.0.1 --port 8001 --reload
```

### 문제: Agent 실행 실패 (result 비어있음)

**원인**: Input 데이터 형식 불일치

**해결**:
```python
# agent의 input_schema() 확인
curl http://localhost:8001/api/agents/sourcing/schema
```

### 문제: "pricing_agent.py not found"

**해결**: 현재 Pricing Agent는 미구현 상태입니다. API에서 제거하거나 나중에 구현 예정.

---

## 📞 Support

- GitHub Issues: https://github.com/fortimove/Fortimove-OS/issues
- Documentation: /docs/
- Email: support@fortimove.com
