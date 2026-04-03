#!/bin/bash
# Daily Scout Integration API 테스트 스크립트

echo "======================================================================"
echo "  Daily Scout Integration API 테스트"
echo "======================================================================"
echo ""

# 1. DB에서 pending 상품 1개 조회
echo "1. Pending 상품 조회 (DB)"
docker exec image-localization-system-db-1 psql -U fortimove -d fortimove_images -c "
SELECT id, product_name, price, url
FROM wellness_products
WHERE workflow_status = 'pending'
LIMIT 1;
" -t | while read -r line; do
    if [ ! -z "$line" ]; then
        echo "   $line"
    fi
done

echo ""
echo "2. PM Agent API를 통한 워크플로우 실행 테스트"

# 테스트 데이터
PRODUCT_NAME="스테인리스 텀블러"
SOURCE_URL="https://item.taobao.com/item.htm?id=987654321"

# API 호출
curl -s -X POST https://staging-pm-agent.fortimove.com/api/workflows/run \
  -H "Content-Type: application/json" \
  -d "{
    \"workflow_name\": \"quick_sourcing_check\",
    \"user_input\": {
      \"source_url\": \"$SOURCE_URL\",
      \"source_title\": \"$PRODUCT_NAME\",
      \"market\": \"korea\",
      \"source_price_cny\": 30.0,
      \"weight_kg\": 0.5,
      \"exchange_rate\": 195.0,
      \"target_margin_rate\": 0.4
    },
    \"save_to_queue\": true
  }" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(f'''
   ✅ API 호출 성공
   실행 ID: {d['execution_id']}
   상태: {d['status']}

   단계별 결과:''')
    for step_id, result in d.get('result', {}).items():
        status_icon = '✅' if result['status'] == 'completed' else '❌'
        print(f'   {status_icon} {step_id}: {result[\"status\"]}')
        if result.get('error'):
            print(f'      에러: {result[\"error\"]}')
except Exception as e:
    print(f'   ❌ 오류: {e}')
    print(sys.stdin.read())
"

echo ""
echo "3. Approval Queue 확인"
curl -s https://staging-pm-agent.fortimove.com/api/stats | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'''
   Pending: {d['pending']}개
   Total: {d['total']}개
''')
"

echo ""
echo "======================================================================"
echo "  테스트 완료"
echo "======================================================================"
