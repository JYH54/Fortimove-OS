# Auth & Handoff Hardening MVP - 예시 응답

## 1. Unauthorized 요청 (401)

```json
// Request: GET /api/queue
// Headers: (No X-API-TOKEN)

{
  "detail": "Invalid or missing API Token"
}
```

```json
// Request: GET /api/queue
// Headers: X-API-TOKEN=wrong_token

{
  "detail": "Invalid or missing API Token"
}
```

```json
// Request: GET /api/queue
// Headers: (No X-API-TOKEN)
// Environment: ADMIN_TOKEN not set, ALLOW_LOCAL_NOAUTH not set

{
  "detail": "ADMIN_TOKEN not configured on server. Access denied."
}
```

---

## 2. Authorized Export (200)

```json
// Request: GET /api/queue/{review_id}/export/json
// Headers: X-API-TOKEN=valid_token

{
  "review_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "revision_id": "rev-uuid-123",
  "revision_number": 2,
  "export_timestamp": "2026-03-30T12:34:56.789012",
  "data": {
    "registration_title_ko": "프리미엄 스테인리스 텀블러 500ml",
    "normalized_options_ko": ["블랙", "화이트", "실버"],
    "key_attributes_summary": {
      "브랜드": "Fortimove",
      "용량": "500ml",
      "재질": "스테인리스"
    },
    "short_description_ko": "보온보냉 기능이 뛰어난 휴대용 텀블러입니다.",
    "registration_status": "ready",
    "needs_human_review": false,
    "hold_reason": null,
    "reject_reason": null,
    "risk_notes": [],
    "suggested_next_action": "마켓(스마트스토어 등) 등록 진행"
  }
}
```

```json
// Request: GET /api/exports/approved/json
// Headers: X-API-TOKEN=valid_token

{
  "batch_id": "20260330_123456",
  "export_timestamp": "2026-03-30T12:34:56.789012",
  "count": 3,
  "items": [
    {
      "review_id": "review-1",
      "revision_id": "rev-1",
      "revision_number": 1,
      "source_title": "不锈钢保温杯",
      "registration_title_ko": "스테인리스 보온 텀블러",
      "normalized_options_ko": ["블랙", "화이트"],
      "short_description_ko": "보온보냉 기능이 있는 휴대용 텀블러",
      "registration_status": "ready",
      "risk_notes": [],
      "reviewer_status": "approved",
      "reviewer_note": "",
      "updated_at": "2026-03-30T12:00:00"
    },
    // ... 2 more items
  ]
}
```

---

## 3. No-Op Handoff (200) - 승인 아이템 0개

```json
// Request: POST /api/handoff/run
// Headers: X-API-TOKEN=valid_token
// Context: No approved items in queue

{
  "success": true,
  "count": 0,
  "mode": "log_only",
  "overall_result": "no_op",
  "summary": "No approved items to handoff",
  "slack": {
    "status": "no_op",
    "message": "No items to send"
  },
  "email": {
    "status": "no_op",
    "message": "No items to send"
  },
  "timestamp": "2026-03-30T12:34:56.789012"
}
```

---

## 4. Log-Only Handoff (200) - SLACK_WEBHOOK_URL, SMTP_HOST 미설정

```json
// Request: POST /api/handoff/run
// Headers: X-API-TOKEN=valid_token
// Context: 3 approved items, no Slack/SMTP configured

{
  "success": true,
  "count": 3,
  "mode": "log_only",
  "overall_result": "success_log_only",
  "summary": "Handoff logged for 3 items",
  "slack": {
    "status": "log_only",
    "message": {
      "text": "🚀 *[Fortimove Admin] Approved Batch Export Summary*",
      "attachments": [
        {
          "color": "#36a64f",
          "fields": [
            {
              "title": "Total Approved Items",
              "value": "3",
              "short": true
            },
            {
              "title": "Export Time (UTC)",
              "value": "2026-03-30T12:34:56.789012",
              "short": true
            }
          ],
          "text": "승인된 상품 리스트 프리뷰:\n• 스테인리스 보온 텀블러 (Rev 1)\n• 프리미엄 무선 이어폰 (Rev 2)\n• 고급 요가 매트 (Rev 1)"
        }
      ]
    }
  },
  "email": {
    "status": "log_only",
    "email": {
      "subject": "[Fortimove] Approved Items Batch Export Summary (3 items)",
      "body": "안녕하세요, Fortimove 관리자입니다.\n\n승인 완료된 상품 3건에 대한 일괄 추출 요약입니다.\n추출 시각: 2026-03-30T12:34:56.789012 (UTC)\n\n상세 데이터는 시스템 대시보드 또는 일괄 CSV 추출을 통해 확인해 주세요.\n\n---\n본 메일은 시스템에 의해 자동 발송되었습니다.",
      "count": 3
    }
  },
  "timestamp": "2026-03-30T12:34:56.789012"
}
```

---

## 5. Real-Send Handoff (200) - SLACK_WEBHOOK_URL, SMTP_HOST 설정됨

### 5-1. Slack/Email 모두 성공

```json
// Request: POST /api/handoff/run
// Headers: X-API-TOKEN=valid_token
// Context: SLACK_WEBHOOK_URL, SMTP configured, both succeed

{
  "success": true,
  "count": 5,
  "mode": "real_send",
  "overall_result": "success",
  "summary": "Handoff executed for 5 items",
  "slack": {
    "status": "sent",
    "message": {
      "text": "🚀 *[Fortimove Admin] Approved Batch Export Summary*",
      "attachments": [
        {
          "color": "#36a64f",
          "fields": [
            {
              "title": "Total Approved Items",
              "value": "5",
              "short": true
            },
            {
              "title": "Export Time (UTC)",
              "value": "2026-03-30T12:34:56.789012",
              "short": true
            }
          ],
          "text": "승인된 상품 리스트 프리뷰:\n• 스테인리스 보온 텀블러 (Rev 1)\n• 프리미엄 무선 이어폰 (Rev 2)\n• 고급 요가 매트 (Rev 1)\n...외 2건"
        }
      ]
    }
  },
  "email": {
    "status": "sent",
    "email": {
      "subject": "[Fortimove] Approved Items Batch Export Summary (5 items)",
      "body": "안녕하세요, Fortimove 관리자입니다.\n\n승인 완료된 상품 5건에 대한 일괄 추출 요약입니다.\n추출 시각: 2026-03-30T12:34:56.789012 (UTC)\n\n상세 데이터는 시스템 대시보드 또는 일괄 CSV 추출을 통해 확인해 주세요.\n\n---\n본 메일은 시스템에 의해 자동 발송되었습니다.",
      "count": 5
    }
  },
  "timestamp": "2026-03-30T12:34:56.789012"
}
```

### 5-2. Slack 성공, Email 실패 (Partial)

```json
// Request: POST /api/handoff/run
// Context: Slack sent, SMTP connection failed

{
  "success": true,
  "count": 5,
  "mode": "real_send",
  "overall_result": "partial",
  "summary": "Handoff executed for 5 items",
  "slack": {
    "status": "sent",
    "message": { /* ... */ }
  },
  "email": {
    "status": "failed",
    "error": "Connection to SMTP server timed out"
  },
  "timestamp": "2026-03-30T12:34:56.789012"
}
```

### 5-3. Slack/Email 모두 실패

```json
// Request: POST /api/handoff/run
// Context: Both Slack and Email failed

{
  "success": false,
  "count": 5,
  "mode": "real_send",
  "overall_result": "failed",
  "summary": "Handoff executed for 5 items",
  "slack": {
    "status": "failed",
    "error": "Slack webhook returned 404: URL not found"
  },
  "email": {
    "status": "failed",
    "error": "SMTP authentication failed"
  },
  "timestamp": "2026-03-30T12:34:56.789012"
}
```

---

## 6. Handoff Status (200) - 최근 실행 이력

```json
// Request: GET /api/handoff/status
// Headers: X-API-TOKEN=valid_token

[
  {
    "log_id": "log-uuid-1",
    "timestamp": "2026-03-30T14:30:00.123456",
    "item_count": 5,
    "export_generated": 1,
    "slack_status": "sent",
    "slack_error": null,
    "email_status": "sent",
    "email_error": null,
    "mode": "real_send"
  },
  {
    "log_id": "log-uuid-2",
    "timestamp": "2026-03-30T10:15:00.123456",
    "item_count": 3,
    "export_generated": 1,
    "slack_status": "sent",
    "slack_error": null,
    "email_status": "failed",
    "email_error": "SMTP connection timeout",
    "mode": "real_send"
  },
  {
    "log_id": "log-uuid-3",
    "timestamp": "2026-03-30T08:00:00.123456",
    "item_count": 0,
    "export_generated": 0,
    "slack_status": "no_op",
    "slack_error": null,
    "email_status": "no_op",
    "email_error": null,
    "mode": "log_only"
  },
  {
    "log_id": "log-uuid-4",
    "timestamp": "2026-03-29T22:45:00.123456",
    "item_count": 2,
    "export_generated": 1,
    "slack_status": "log_only",
    "slack_error": null,
    "email_status": "log_only",
    "email_error": null,
    "mode": "log_only"
  },
  {
    "log_id": "log-uuid-5",
    "timestamp": "2026-03-29T18:30:00.123456",
    "item_count": 10,
    "export_generated": 1,
    "slack_status": "sent",
    "slack_error": null,
    "email_status": "sent",
    "email_error": null,
    "mode": "real_send"
  }
]
```

---

## 7. CSV Export 예시

```csv
// Request: GET /api/exports/approved/csv
// Headers: X-API-TOKEN=valid_token

review_id,revision_number,source_title,registration_title_ko,registration_status,short_description_ko,normalized_options
a1b2c3d4-1234,1,不锈钢保温杯,스테인리스 보온 텀블러,ready,보온보냉 기능이 있는 휴대용 텀블러,"블랙, 화이트, 실버"
a1b2c3d4-5678,2,无线耳机,프리미엄 무선 이어폰,ready,노이즈 캔슬링 기능이 탑재된 무선 이어폰,"블랙, 화이트"
a1b2c3d4-9012,1,瑜伽垫,고급 요가 매트,ready,미끄럼 방지 기능이 있는 두께 8mm 요가 매트,"퍼플, 핑크, 그린"
```

---

## 8. 환경 변수 설정에 따른 동작 변화

### Case 1: Production (보안 최대)
```bash
ADMIN_TOKEN=strong_secret_token_xyz
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=ops@fortimove.com
SMTP_PASS=email_password
EMAIL_FROM=ops@fortimove.com
EMAIL_TO=team@fortimove.com
```
→ **모든 엔드포인트 보호**, **실제 Slack/Email 전송**

### Case 2: Staging (log_only 모드)
```bash
ADMIN_TOKEN=staging_token
# SLACK_WEBHOOK_URL not set
# SMTP_HOST not set
```
→ **모든 엔드포인트 보호**, **log_only 모드 (전송 안함)**

### Case 3: Local Development (보호 해제)
```bash
ALLOW_LOCAL_NOAUTH=true
# ADMIN_TOKEN not set
# SLACK_WEBHOOK_URL not set
# SMTP_HOST not set
```
→ **모든 엔드포인트 보호 해제**, **log_only 모드**

### Case 4: 안전하지 않은 설정 (차단됨)
```bash
# ADMIN_TOKEN not set
# ALLOW_LOCAL_NOAUTH not set
```
→ **모든 보호된 엔드포인트 401 반환** (`ADMIN_TOKEN not configured on server. Access denied.`)
