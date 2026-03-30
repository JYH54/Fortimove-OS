import json
import logging
import os
import csv
import io
import httpx
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class HandoffService:
    def __init__(self):
        self.slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        self.smtp_host = os.getenv("SMTP_HOST")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER")
        self.smtp_pass = os.getenv("SMTP_PASS")
        self.email_from = os.getenv("EMAIL_FROM", "admin@fortimove.com")
        self.email_to = os.getenv("EMAIL_TO", "ops@fortimove.com")
        self.log_only = not (self.slack_webhook_url or self.smtp_host)

    def generate_batch_json(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """승인된 아이템들을 JSON 배치 포맷으로 변환합니다."""
        export_items = []
        for item in items:
            data = item.get('revised_agent_output', item.get('raw_agent_output', {}))
            export_items.append({
                "review_id": item['review_id'],
                "revision_id": item.get('revision_id'),
                "revision_number": item.get('revision_number'),
                "source_title": item.get('source_title'),
                "registration_title_ko": data.get("registration_title_ko"),
                "normalized_options_ko": data.get("normalized_options_ko", []),
                "short_description_ko": data.get("short_description_ko"),
                "registration_status": data.get("registration_status"),
                "risk_notes": data.get("risk_notes", []),
                "reviewer_status": item.get('reviewer_status'),
                "reviewer_note": item.get('reviewer_note'),
                "updated_at": item.get('updated_at')
            })
        
        return {
            "batch_id": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            "export_timestamp": datetime.utcnow().isoformat(),
            "count": len(export_items),
            "items": export_items
        }

    def generate_batch_csv(self, items: List[Dict[str, Any]]) -> str:
        """승인된 아이템들을 CSV 문자열로 변환합니다."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        header = [
            "review_id", "revision_number", "source_title", 
            "registration_title_ko", "registration_status", 
            "short_description_ko", "normalized_options"
        ]
        writer.writerow(header)
        
        for item in items:
            data = item.get('revised_agent_output', item.get('raw_agent_output', {}))
            writer.writerow([
                item['review_id'],
                item.get('revision_number'),
                item.get('source_title'),
                data.get("registration_title_ko"),
                data.get("registration_status"),
                data.get("short_description_ko"),
                ", ".join(data.get("normalized_options_ko", []))
            ])
            
        return output.getvalue()

    def send_slack_summary(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Slack으로 승인 현황 요약을 전송합니다."""
        count = len(items)
        timestamp = datetime.utcnow().isoformat()
        
        preview_text = ""
        if count > 0:
            previews = []
            for item in items[:3]:
                data = item.get('revised_agent_output', {})
                title = data.get("registration_title_ko") or item.get("source_title")
                previews.append(f"• {title} (Rev {item.get('revision_number')})")
            preview_text = "\n" + "\n".join(previews)
            if count > 3:
                preview_text += f"\n...외 {count-3}건"

        message = {
            "text": f"🚀 *[Fortimove Admin] Approved Batch Export Summary*",
            "attachments": [
                {
                    "color": "#36a64f",
                    "fields": [
                        {"title": "Total Approved Items", "value": str(count), "short": True},
                        {"title": "Export Time (UTC)", "value": timestamp, "short": True}
                    ],
                    "text": f"승인된 상품 리스트 프리뷰:{preview_text}" if count > 0 else "승인된 대기 상품이 없습니다."
                }
            ]
        }

        if self.log_only:
            logger.info(f"[LOG_ONLY] Slack Webhook Message:\n{json.dumps(message, indent=2, ensure_ascii=False)}")
            return {"status": "log_only", "message": message}
        
        if not self.slack_webhook_url:
            return {"status": "failed", "error": "SLACK_WEBHOOK_URL not configured"}

        try:
            logger.info(f"Sending Slack webhook to {self.slack_webhook_url}")
            with httpx.Client(timeout=10.0) as client:
                res = client.post(self.slack_webhook_url, json=message)
                res.raise_for_status()
            return {"status": "sent", "message": message}
        except Exception as e:
            logger.error(f"Slack sending failed: {e}")
            return {"status": "failed", "error": str(e)}

    def send_email_summary(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Email로 승인 현황 요약을 전송합니다."""
        count = len(items)
        subject = f"[Fortimove] Approved Items Batch Export Summary ({count} items)"
        
        body = f"안녕하세요, Fortimove 관리자입니다.\n\n"
        body += f"승인 완료된 상품 {count}건에 대한 일괄 추출 요약입니다.\n"
        body += f"추출 시각: {datetime.utcnow().isoformat()} (UTC)\n\n"
        
        if count > 0:
            body += "상세 데이터는 시스템 대시보드 또는 일괄 CSV 추출을 통해 확인해 주세요.\n"
        else:
            body += "현재 추출할 승인 대기 상품이 없습니다.\n"
            
        body += "\n---\n본 메일은 시스템에 의해 자동 발송되었습니다."

        email_data = {
            "subject": subject,
            "body": body,
            "count": count
        }

        if self.log_only:
            logger.info(f"[LOG_ONLY] Email Summary:\nSubject: {subject}\nBody: {body}")
            return {"status": "log_only", "email": email_data}
            
        if not self.smtp_host:
            return {"status": "failed", "error": "SMTP_HOST not configured"}

        try:
            logger.info(f"Sending Email to SMTP host {self.smtp_host}")
            msg = MIMEText(body)
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = self.email_to

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10.0) as server:
                if self.smtp_port == 587:
                    server.starttls()
                if self.smtp_user and self.smtp_pass:
                    server.login(self.smtp_user, self.smtp_pass)
                server.send_message(msg)
            return {"status": "sent", "email": email_data}
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return {"status": "failed", "error": str(e)}
