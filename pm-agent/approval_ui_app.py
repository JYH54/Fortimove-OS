from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import csv
import io
import os
from pathlib import Path

# Load environment variables from .env file manually
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

from datetime import datetime
from approval_queue import ApprovalQueueManager
from handoff_service import HandoffService
from agent_status_tracker import AgentStatusTracker

# JWT Auth imports
from auth import get_current_user, require_operator_or_admin, require_admin, TokenPayload
from auth_router import router as auth_router

app = FastAPI(
    title="Fortimove PM Agent Dashboard",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8001").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

handoff_service = HandoffService()

# 에이전트를 먼저 등록 (anthropic SDK 호환 문제 시 graceful skip)
try:
    from real_agents import register_real_agents
    from cs_agent import register_cs_agent
    from product_registration_agent import register_product_registration_agent

    registry = register_real_agents()
    register_cs_agent(registry)
    register_product_registration_agent(registry)
except Exception as e:
    import logging
    logging.getLogger(__name__).warning(f"에이전트 등록 실패 (대시보드는 정상 동작): {e}")

# 이제 agent_tracker 초기화
agent_tracker = AgentStatusTracker()

# Auth Router (JWT 인증 API)
app.include_router(auth_router)

# API Execution Router 추가
from api_execution import router as execution_router
app.include_router(execution_router)

# Phase 3 Dashboard APIs 추가
from phase3_dashboard_apis import router as phase3_router
app.include_router(phase3_router)

# Premium API (상세페이지, 키워드, 리뷰, 캐시)
from premium_api import router as premium_router
app.include_router(premium_router)

# Monitoring (Sentry + Prometheus)
from monitoring import setup_monitoring
setup_monitoring(app)

# JWT 기반 인증으로 전환 (기존 ADMIN_TOKEN 하위 호환 유지)
# verify_admin_token은 get_current_user로 대체됨
verify_admin_token = get_current_user

@app.get("/health")
def health_check():
    """Liveness probe — 서비스가 살아있는지 확인"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/health/ready")
def readiness_check():
    """Readiness probe — 서비스가 트래픽을 받을 준비가 되었는지 확인"""
    checks = {}

    # DB 연결 확인
    try:
        aq = ApprovalQueueManager()
        aq.list_items("pending")
        checks["database"] = "ready"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # 에이전트 레지스트리 확인
    checks["agents"] = f"{len(agent_tracker.get_all_agent_status())} registered"
    checks["auth"] = "ready"

    all_ready = all(v == "ready" or "registered" in str(v) for v in checks.values())

    return {
        "status": "ready" if all_ready else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "checks": checks
    }

class ReviewUpdateRequest(BaseModel):
    reviewer_status: str
    reviewer_note: Optional[str] = ""

# Dependency injection for easy testing/overriding
def get_aq() -> ApprovalQueueManager:
    return ApprovalQueueManager()

@app.get("/api/stats")
def get_queue_stats(aq: ApprovalQueueManager = Depends(get_aq)):
    """Queue 상태별 통계 조회 (인증 불필요 - 공개 API)"""
    try:
        stats = {
            "pending": len(aq.list_items("pending")),
            "approved": len(aq.list_items("approved")),
            "needs_edit": len(aq.list_items("needs_edit")),
            "rejected": len(aq.list_items("rejected"))
        }
        stats["total"] = sum(stats.values())
        return stats
    except Exception as e:
        # 에러 시에도 0으로 반환 (UI 깨지지 않도록)
        return {
            "pending": 0,
            "approved": 0,
            "needs_edit": 0,
            "rejected": 0,
            "total": 0
        }

# Agent Status API Endpoints (공개 API - 인증 불필요)
@app.get("/api/agents/status")
def get_all_agents_status():
    """모든 에이전트의 실시간 상태 조회"""
    return agent_tracker.get_all_agent_status()

@app.get("/api/agents/status/{agent_name}")
def get_agent_status(agent_name: str):
    """특정 에이전트 상태 조회"""
    status = agent_tracker.get_agent_status(agent_name)
    if not status:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    return status

@app.get("/api/agents/statistics")
def get_agent_statistics():
    """에이전트 통합 통계 조회"""
    return agent_tracker.get_statistics()

@app.get("/api/workflows/history")
def get_workflow_history(limit: int = 20):
    """Workflow 실행 이력 조회"""
    return agent_tracker.get_workflow_history(limit)

@app.get("/api/workflows/{workflow_id}")
def get_workflow_detail(workflow_id: str):
    """특정 Workflow 상세 조회"""
    workflow = agent_tracker.get_workflow_by_id(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return workflow

@app.get("/api/queue", dependencies=[Depends(verify_admin_token)])
def list_queue(status: str = "pending", aq: ApprovalQueueManager = Depends(get_aq)):
    try:
        items = aq.list_items(status)
        return items
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/queue/{review_id}", dependencies=[Depends(verify_admin_token)])
def get_queue_item(review_id: str, aq: ApprovalQueueManager = Depends(get_aq)):
    item = aq.get_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
    return item

@app.patch("/api/queue/{review_id}", dependencies=[Depends(verify_admin_token)])
def update_queue_item(review_id: str, update: ReviewUpdateRequest, aq: ApprovalQueueManager = Depends(get_aq)):
    try:
        aq.update_reviewer_status(review_id, update.reviewer_status, update.reviewer_note)
        return {"success": True, "message": f"Updated to {update.reviewer_status}"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Review item not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/queue/{review_id}/retry", dependencies=[Depends(verify_admin_token)])
def retry_review_item(review_id: str, aq: ApprovalQueueManager = Depends(get_aq)):
    from product_registration_agent import ProductRegistrationAgent
    item = aq.get_item(review_id)
    if not item:
        raise HTTPException(status_code=404, detail="Review item not found")
        
    if item['reviewer_status'] != 'needs_edit':
        raise HTTPException(status_code=400, detail="Only 'needs_edit' items can be retried")
    
    reviewer_note = item.get('reviewer_note')
    validation_error = aq.validate_reviewer_note(reviewer_note)
    if validation_error:
        raise HTTPException(status_code=400, detail=validation_error)

    # 1. Get latest output (either from revisions or the original one)
    latest_rev = aq.get_latest_revision(review_id)
    previous_output = latest_rev['revised_agent_output'] if latest_rev else item['raw_agent_output']
    
    # 2. Create pending revision
    try:
        source_snapshot = item['source_data']
        revision_id = aq.create_revision_pending(
            review_id=review_id,
            source_snapshot=source_snapshot,
            previous_output=previous_output,
            reviewer_note=item['reviewer_note']
        )
    except ConnectionError as ce:
        raise HTTPException(status_code=409, detail=str(ce))

    # 3. Execute Agent
    agent = ProductRegistrationAgent()
    try:
        # We need to map the combined input for the agent
        retry_input = item['source_data'].copy()
        retry_input.update({
            "reviewer_note": item['reviewer_note'],
            "previous_output": previous_output
        })
        # agent.execute returns TaskResult. result.output is our dict.
        task_result = agent.execute(retry_input)
        
        if task_result.is_success():
            aq.complete_revision(revision_id, task_result.output, "completed")
            return {"success": True, "revision_id": revision_id, "output": task_result.output}
        else:
            aq.complete_revision(revision_id, None, "failed")
            raise HTTPException(status_code=500, detail=f"Agent Execution Failed: {task_result.error}")
            
    except Exception as e:
        aq.complete_revision(revision_id, None, "failed")
        raise HTTPException(status_code=500, detail=f"Unexpected Error during retry: {str(e)}")

@app.get("/api/queue/{review_id}/revisions", dependencies=[Depends(verify_admin_token)])
def list_item_revisions(review_id: str, aq: ApprovalQueueManager = Depends(get_aq)):
    return aq.list_revisions(review_id)

@app.get("/api/queue/{review_id}/export/json", dependencies=[Depends(verify_admin_token)])
def export_json(review_id: str, aq: ApprovalQueueManager = Depends(get_aq)):
    item = aq.get_item(review_id)
    if not item or item['reviewer_status'] != 'approved':
        raise HTTPException(status_code=400, detail="Only approved items can be exported")
    
    latest_rev = aq.get_latest_revision(review_id)
    # Revision 1이 이미 실체화되어 있으므로 latest_rev는 항상 존재해야 함
    data = latest_rev['revised_agent_output'] if latest_rev else item['raw_agent_output']
    
    export_payload = {
        "review_id": review_id,
        "revision_id": latest_rev['revision_id'] if latest_rev else "original",
        "revision_number": latest_rev['revision_number'] if latest_rev else 1,
        "export_timestamp": datetime.utcnow().isoformat(),
        "data": data
    }
    return export_payload

@app.get("/api/queue/{review_id}/export/csv", dependencies=[Depends(verify_admin_token)])
def export_csv(review_id: str, aq: ApprovalQueueManager = Depends(get_aq)):
    item = aq.get_item(review_id)
    if not item or item['reviewer_status'] != 'approved':
        raise HTTPException(status_code=400, detail="Only approved items can be exported")
    
    latest_rev = aq.get_latest_revision(review_id)
    data = latest_rev['revised_agent_output'] if latest_rev else item['raw_agent_output']
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    fields = [
        "review_id", "revision_number", "source_title", 
        "registration_title_ko", "registration_status", 
        "short_description_ko", "normalized_options"
    ]
    writer.writerow(fields)
    
    # Row
    writer.writerow([
        review_id,
        latest_rev['revision_number'] if latest_rev else 1,
        item.get("source_title"),
        data.get("registration_title_ko"),
        data.get("registration_status"),
        data.get("short_description_ko"),
        ", ".join(data.get("normalized_options_ko", []))
    ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=export_{review_id}.csv"}
    )

@app.get("/api/exports/approved/json", dependencies=[Depends(verify_admin_token)])
def export_batch_json(aq: ApprovalQueueManager = Depends(get_aq)):
    items = aq.get_latest_approved_items()
    payload = handoff_service.generate_batch_json(items)
    return payload

@app.get("/api/exports/approved/csv", dependencies=[Depends(verify_admin_token)])
def export_batch_csv(aq: ApprovalQueueManager = Depends(get_aq)):
    items = aq.get_latest_approved_items()
    csv_content = handoff_service.generate_batch_csv(items)
    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=approved_batch.csv"}
    )

@app.get("/api/handoff/status", dependencies=[Depends(verify_admin_token)])
def get_handoff_status(aq: ApprovalQueueManager = Depends(get_aq)):
    return aq.get_handoff_history(limit=5)

@app.get("/api/handoff/runs", dependencies=[Depends(verify_admin_token)])
def get_handoff_runs(aq: ApprovalQueueManager = Depends(get_aq)):
    """Get recent handoff run history including in-progress status."""
    return {
        "current_run": aq.get_current_handoff_run(),
        "recent_runs": aq.get_handoff_run_history(limit=10)
    }

@app.get("/api/handoff/verify", dependencies=[Depends(verify_admin_token)])
def verify_handoff_channels():
    """Verify Slack and Email channel configuration and connectivity."""
    import os

    # Check environment variables
    slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")

    mode = 'log_only' if not (slack_webhook or smtp_host) else 'real_send'

    # Verify Slack
    slack_result = {"channel": "slack", "configured": bool(slack_webhook)}
    if slack_webhook:
        try:
            # Test Slack webhook with minimal payload
            import httpx
            test_payload = {
                "text": "[Fortimove Test] Slack channel verification test",
                "attachments": [{
                    "color": "#36a64f",
                    "text": "This is a test message to verify Slack integration. You can ignore this."
                }]
            }
            response = httpx.post(slack_webhook, json=test_payload, timeout=10.0)
            if response.status_code == 200:
                slack_result["status"] = "verified"
                slack_result["message"] = "Slack webhook is working correctly"
            else:
                slack_result["status"] = "failed"
                slack_result["error"] = f"Slack returned status {response.status_code}"
        except Exception as e:
            slack_result["status"] = "failed"
            slack_result["error"] = str(e)
    else:
        slack_result["status"] = "not_verified"
        slack_result["message"] = "SLACK_WEBHOOK_URL not configured"

    # Verify Email
    email_result = {"channel": "email", "configured": bool(smtp_host)}
    if smtp_host:
        try:
            # Test SMTP connection
            import smtplib
            with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                if smtp_port == 587:
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                email_result["status"] = "verified"
                email_result["message"] = f"SMTP connection to {smtp_host}:{smtp_port} successful"
        except Exception as e:
            email_result["status"] = "failed"
            email_result["error"] = str(e)
    else:
        email_result["status"] = "not_verified"
        email_result["message"] = "SMTP_HOST not configured"

    return {
        "mode": mode,
        "slack": slack_result,
        "email": email_result,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/api/handoff/run", dependencies=[Depends(verify_admin_token)])
def run_handoff(aq: ApprovalQueueManager = Depends(get_aq)):
    mode = 'log_only' if handoff_service.log_only else 'real_send'

    # Start handoff run (duplicate prevention happens here)
    run_id = aq.start_handoff_run(mode)

    try:
        items = aq.get_latest_approved_items()
        item_count = len(items)

        # Safe no-op if no approved items
        if item_count == 0:
            aq.create_handoff_log(
                item_count=0,
                export_generated=False,
                slack_status='no_op',
                slack_error=None,
                email_status='no_op',
                email_error=None,
                mode=mode
            )
            aq.finish_handoff_run(
                run_id=run_id,
                status='no_op',
                item_count=0,
                slack_status='no_op',
                email_status='no_op',
                overall_result='no_op'
            )
            return {
                "success": True,
                "run_id": run_id,
                "count": 0,
                "mode": mode,
                "overall_result": "no_op",
                "summary": "No approved items to handoff",
                "slack": {"status": "no_op", "message": "No items to send"},
                "email": {"status": "no_op", "message": "No items to send"},
                "timestamp": datetime.utcnow().isoformat()
            }

        # Execute handoff
        slack_res = handoff_service.send_slack_summary(items)
        email_res = handoff_service.send_email_summary(items)

        # Determine overall result
        slack_status = slack_res.get('status', 'failed')
        email_status = email_res.get('status', 'failed')

        # Overall result logic:
        # - If both succeeded or log_only: success
        # - If one failed: partial
        # - If both failed: failed
        if handoff_service.log_only:
            overall_result = "success_log_only"
        elif slack_status == "sent" and email_status == "sent":
            overall_result = "success"
        elif slack_status in ["sent", "log_only"] or email_status in ["sent", "log_only"]:
            overall_result = "partial"
        else:
            overall_result = "failed"

        # Record metadata
        aq.create_handoff_log(
            item_count=item_count,
            export_generated=True,
            slack_status=slack_status,
            slack_error=slack_res.get('error'),
            email_status=email_status,
            email_error=email_res.get('error'),
            mode=mode
        )

        # Mark run as completed
        aq.finish_handoff_run(
            run_id=run_id,
            status='completed' if overall_result in ['success', 'success_log_only', 'partial'] else 'failed',
            item_count=item_count,
            slack_status=slack_status,
            email_status=email_status,
            overall_result=overall_result
        )

        return {
            "success": overall_result in ["success", "success_log_only", "partial"],
            "run_id": run_id,
            "count": item_count,
            "mode": mode,
            "overall_result": overall_result,
            "summary": f"Handoff {'logged' if handoff_service.log_only else 'executed'} for {item_count} items",
            "slack": slack_res,
            "email": email_res,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        # Mark run as failed
        aq.finish_handoff_run(
            run_id=run_id,
            status='failed',
            item_count=0,
            slack_status='failed',
            email_status='failed',
            overall_result='failed',
            error_message=str(e)
        )
        raise

# OLD ROUTE - Replaced with Template-based Agent Console (see line 1613)
# @app.get("/", response_class=HTMLResponse)
def index_old():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Approval Queue MVP</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; height: 100vh; margin: 0; background: #f9fafb; color: #111827;}
            .sidebar { width: 420px; border-right: 1px solid #e5e7eb; padding: 20px; overflow-y: auto; background: #fff;}
            .main { flex: 1; padding: 20px; overflow-y: auto; }
            .item-card { padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
            .item-card:hover { border-color: #3b82f6; background: #eff6ff;}
            .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
            .badge.hold { background: #fee2e2; color: #991b1b; }
            .badge.ready { background: #dcfce3; color: #166534; }
            pre { background: #1f2937; color: #e5e7eb; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px;}
            .btn { cursor: pointer; padding: 8px 16px; border: none; border-radius: 6px; font-weight: 600; color: white; transition: 0.2s;}
            .btn:hover { opacity: 0.9; transform: translateY(-1px); }
            .btn:disabled { opacity: 0.5; cursor: not-allowed; }
            .btn-blue { background: #3b82f6; }
            .btn-green { background: #10b981; }
            .btn-red { background: #ef4444; }
            .actions-bar { margin-top: 20px; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; background: white;}
            .batch-box { margin-top: 25px; padding: 15px; background: #fdf2f2; border: 1px solid #fecaca; border-radius: 8px; font-size: 13px;}
            .settings-box { border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px; font-size: 12px; color: #4b5563; }
            .status-badge { font-size: 10px; padding: 2px 4px; border-radius: 3px; background: #e5e7eb; margin-left: 5px; }
            textarea { width: 100%; height: 80px; margin-bottom: 10px; padding: 8px; border-radius: 4px; border: 1px solid #d1d5db;}
            .summary-card { background: #f9fafb; border: 2px solid #e5e7eb; border-radius: 12px; padding: 20px; margin-bottom: 20px; }
            @keyframes slideInRight { from { opacity: 0; transform: translateX(100px); } to { opacity: 1; transform: translateX(0); } }
            @keyframes slideOutRight { from { opacity: 1; transform: translateX(0); } to { opacity: 0; transform: translateX(100px); } }
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h2 style="margin:0;">승인 대기열</h2>
                <a href="/health" target="_blank" style="font-size: 10px; color: #10b981; text-decoration: none;">● System Healthy</a>
            </div>

            <!-- Navigation -->
            <div style="display: flex; gap: 8px; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb;">
                <a href="/" style="padding: 8px 16px; background: #3b82f6; color: white; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600;">승인 대기열</a>
                <a href="/agents" style="padding: 8px 16px; background: #f3f4f6; color: #4b5563; border-radius: 6px; text-decoration: none; font-size: 12px; font-weight: 600; transition: 0.2s;" onmouseover="this.style.background='#e5e7eb'" onmouseout="this.style.background='#f3f4f6'">🤖 에이전트</a>
            </div>

            <div style="margin: 15px 0;">
                <label style="font-size:12px; font-weight:600; color:#4b5563; display:block; margin-bottom:6px;">
                    상태 필터
                </label>
                <select id="statusFilter" onchange="loadItems()" style="width:100%; padding:10px; border-radius:6px; border:1px solid #d1d5db; font-size:14px;">
                    <option value="pending" selected>⏳ Pending</option>
                    <option value="approved">✅ Approved</option>
                    <option value="needs_edit">✏️ Needs Edit</option>
                    <option value="rejected">🚫 Rejected</option>
                </select>

                <!-- Status count summary -->
                <div id="statusSummary" style="margin-top:10px; padding:12px; background:#f9fafb; border-radius:6px; font-size:11px; color:#6b7280;">
                    Loading statistics...
                </div>
            </div>

            <div id="itemList"></div>

            <div class="batch-box">
                <h3 style="margin-top:0;">Batch Operations</h3>
                <p style="font-size: 11px; color: #b91c1c; margin-bottom: 10px;">(Latest Approved Items Only)</p>
                
                <button class="btn btn-blue" style="width:100%; margin-bottom:8px; font-size:12px; background:#1f2937;" onclick="downloadExport('/api/exports/approved/json', 'approved_batch.json')">Export Batch JSON</button>
                <button class="btn btn-blue" style="width:100%; margin-bottom:8px; font-size:12px; background:#4b5563;" onclick="downloadExport('/api/exports/approved/csv', 'approved_batch.csv')">Export Batch CSV</button>
                
                <button id="handoffBtn" class="btn btn-red" style="width:100%; font-size:12px;" onclick="runHandoff()">🚀 Run Handoff (Slack/Email)</button>

                <div id="handoffStatus" style="margin-top: 12px; font-size: 11px; color: #6b7280; padding: 8px; background: #fff; border-radius: 4px; border: 1px solid #fecaca;">
                    Loading handoff status...
                </div>

                <button class="btn btn-blue" style="width:100%; margin-top:8px; font-size:11px; background:#6366f1;" onclick="verifyChannels()">🔍 Verify Slack/Email</button>

                <div id="verifyStatus" style="margin-top: 8px; font-size: 10px; color: #6b7280; padding: 6px; background: #f9fafb; border-radius: 4px; display:none;"></div>
            </div>

            <div class="settings-box">
                <h3 style="margin-top:0;">Auth Settings</h3>
                <p>Admin Token <span style="color:#ef4444;">*</span></p>
                <input type="password" id="adminToken" placeholder="Enter Token..." style="width:92%; padding:8px; margin-bottom:10px; border-radius:4px; border:1px solid #d1d5db;">
                <p style="font-size: 10px; color: #9ca3af; margin-top:0;">(Stored in <b>localStorage</b> for this browser only)</p>
                <button class="btn btn-blue" style="font-size:11px; background:#4b5563; padding: 5px 10px;" onclick="saveToken()">Save Token</button>
                <button class="btn" style="font-size:11px; background:#f3f4f6; color:#4b5563; border:1px solid #d1d5db; padding: 5px 10px;" onclick="clearToken()">Clear</button>
            </div>
        </div>
        <div class="main" id="mainContent">
            <h2>Item Details</h2>
            <p>Select an item from the queue to review.</p>
        </div>

        <script>
            let currentItem = null;

            function getToken() {
                return localStorage.getItem('admin_token') || '';
            }

            function saveToken() {
                const token = document.getElementById('adminToken').value.trim();

                // 1. 빈 토큰 검증
                if (!token) {
                    showNotification('❌ 토큰을 입력해주세요.', 'error');
                    return;
                }

                // 2. 토큰 포맷 검증 (간단한 길이 체크)
                if (token.length < 20) {
                    if (!confirm('토큰이 너무 짧습니다. 정말 저장하시겠습니까?')) {
                        return;
                    }
                }

                localStorage.setItem('admin_token', token);

                // 3. 즉시 검증 시도
                showNotification('⏳ 토큰 검증 중...', 'info');

                authenticatedFetch('/api/queue?status=pending')
                    .then(res => {
                        if (res.ok) {
                            showNotification('✅ 토큰 저장 및 인증 성공!', 'success');
                            loadItems();
                            loadHandoffStatus();
                        } else {
                            throw new Error('Unauthorized');
                        }
                    })
                    .catch(err => {
                        showNotification('⚠️ 토큰이 저장되었지만 인증에 실패했습니다. 토큰을 다시 확인해주세요.', 'warning');
                    });
            }

            // Toast Notification Helper
            function showNotification(message, type = 'info') {
                const bgColors = {
                    'success': '#10b981',
                    'error': '#ef4444',
                    'warning': '#f59e0b',
                    'info': '#3b82f6'
                };

                const toast = document.createElement('div');
                toast.style.cssText = `
                    position: fixed; top: 20px; right: 20px; z-index: 9999;
                    background: ${bgColors[type] || bgColors.info};
                    color: white; padding: 16px 24px; border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15); font-weight: 600;
                    animation: slideInRight 0.3s ease; font-size: 14px; max-width: 400px;
                `;
                toast.textContent = message;
                document.body.appendChild(toast);

                setTimeout(() => {
                    toast.style.animation = 'slideOutRight 0.3s ease';
                    setTimeout(() => toast.remove(), 300);
                }, 3000);
            }

            function clearToken() {
                localStorage.removeItem('admin_token');
                document.getElementById('adminToken').value = '';
                alert('Token cleared!');
                loadItems();
            }

            async function authenticatedFetch(url, options = {}) {
                const token = getToken();
                const headers = options.headers || {};
                headers['X-API-TOKEN'] = token;
                
                const response = await fetch(url, { ...options, headers });
                
                if (response.status === 401) {
                    alert('Unauthorized (401): Please check your Admin Token in sidebar.');
                    throw new Error('Unauthorized');
                }
                return response;
            }

            async function loadItems() {
                const status = document.getElementById('statusFilter').value;
                try {
                    const res = await authenticatedFetch('/api/queue?status=' + status);
                    const items = await res.json();

                    const listEl = document.getElementById('itemList');
                    listEl.innerHTML = '';

                    // 통계 새로고침
                    loadStatusSummary();

                    if (items.length === 0) {
                        // 다른 Status 추천
                        const suggestions = {
                            'pending': '⏳ Pending',
                            'approved': '✅ Approved',
                            'needs_edit': '✏️ Needs Edit',
                            'rejected': '🚫 Rejected'
                        };
                        const otherStatuses = Object.keys(suggestions).filter(s => s !== status);
                        const suggestion = otherStatuses[0];

                        listEl.innerHTML = `
                            <div style="text-align:center; padding:40px 20px; color:#6b7280;">
                                <div style="font-size:48px; opacity:0.3;">📭</div>
                                <p style="margin:12px 0 0 0; font-size:14px; font-weight:600;">No items in ${suggestions[status]}</p>
                                <p style="margin:4px 0 16px 0; font-size:12px;">이 상태에는 아이템이 없습니다.</p>
                                <button class="btn btn-blue" onclick="document.getElementById('statusFilter').value='${suggestion}'; loadItems();" style="font-size:13px;">
                                    ${suggestions[suggestion]} 보기 →
                                </button>
                            </div>
                        `;
                        return;
                    }

                    items.forEach(item => {
                        const card = document.createElement('div');
                        card.className = 'item-card';
                        card.innerHTML = `
                            <div style="font-size: 14px; font-weight: bold; margin-bottom: 6px;">${item.registration_title_ko || item.source_title}</div>
                            <span class="badge ${item.registration_status}">${item.registration_status}</span>
                            <div style="font-size: 12px; color: #6b7280; margin-top: 8px;">${item.created_at.substring(0,16)}</div>
                        `;
                        card.onclick = () => loadDetail(item.review_id);
                        listEl.appendChild(card);
                    });
                } catch (e) {
                    // Empty State for auth failure
                    const token = getToken();
                    if (!token || token.length < 10) {
                        document.getElementById('itemList').innerHTML = `
                            <div style="text-align:center; padding:40px 20px; color:#6b7280;">
                                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" style="opacity:0.3; margin:0 auto 16px; display:block;">
                                    <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z" fill="currentColor"/>
                                </svg>
                                <h3 style="margin:0 0 10px 0; font-size:18px; color:#111827;">인증이 필요합니다</h3>
                                <p style="margin:0 0 20px; font-size:14px;">
                                    아래 ⬇️ <b>Auth Settings</b>에서<br>Admin Token을 입력해주세요.
                                </p>
                                <button class="btn btn-blue" onclick="document.getElementById('adminToken').focus(); document.getElementById('adminToken').scrollIntoView({behavior:'smooth', block:'center'});" style="font-size:13px;">
                                    토큰 입력하기 →
                                </button>
                            </div>
                        `;
                    } else {
                        document.getElementById('itemList').innerHTML = '<div style="color:#ef4444; font-size:12px; padding:20px; text-align:center;">❌ Failed to load items.<br>Token may be invalid.</div>';
                    }
                }
            }

            async function loadDetail(id) {
                try {
                    const res = await authenticatedFetch('/api/queue/' + id);
                    currentItem = await res.json();

                    const mainEl = document.getElementById('mainContent');

                    // Risk notes formatting
                    const riskNotesHtml = (currentItem.risk_notes && currentItem.risk_notes.length > 0) ? `
                        <div style="background:#fef2f2; padding:12px; border-radius:6px; border-left:3px solid #ef4444; margin-top:16px;">
                            <b style="color:#991b1b;">⚠️ Risk Notes:</b>
                            <ul style="margin:8px 0 0 0; padding-left:20px; color:#7f1d1d;">
                                ${currentItem.risk_notes.map(note => `<li>${note}</li>`).join('')}
                            </ul>
                        </div>
                    ` : '';

                    // Options formatting
                    const optionsHtml = (currentItem.raw_agent_output.normalized_options_ko && currentItem.raw_agent_output.normalized_options_ko.length > 0) ? `
                        <div style="margin-top:12px;">
                            <b style="font-size:13px; color:#4b5563;">옵션:</b>
                            <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
                                ${currentItem.raw_agent_output.normalized_options_ko.map(opt =>
                                    `<span style="background:#e5e7eb; padding:4px 8px; border-radius:4px; font-size:12px;">${opt}</span>`
                                ).join('')}
                            </div>
                        </div>
                    ` : '';

                    mainEl.innerHTML = `
                        <!-- 핵심 정보 카드 -->
                        <div class="summary-card">
                            <div style="display:flex; justify-content:space-between; align-items:start;">
                                <div style="flex:1;">
                                    <h2 style="margin:0 0 8px 0; font-size:20px;">${currentItem.raw_agent_output.registration_title_ko || currentItem.source_title}</h2>
                                    <div style="font-size:13px; color:#6b7280;">
                                        원본: ${currentItem.source_title}
                                    </div>
                                </div>
                                <span class="badge ${currentItem.registration_status}" style="font-size:14px; padding:6px 12px;">
                                    ${currentItem.registration_status}
                                </span>
                            </div>

                            ${riskNotesHtml}
                            ${optionsHtml}

                            ${currentItem.raw_agent_output.short_description_ko ? `
                                <div style="margin-top:16px; padding-top:16px; border-top:1px solid #e5e7eb;">
                                    <b style="font-size:13px; color:#4b5563;">간단 설명:</b>
                                    <p style="margin:6px 0 0 0; font-size:13px; color:#374151; line-height:1.6;">
                                        ${currentItem.raw_agent_output.short_description_ko}
                                    </p>
                                </div>
                            ` : ''}
                        </div>

                        <!-- 리뷰 액션 바 -->
                        <div class="actions-bar">
                            <h3 style="margin-top:0;">리뷰 결정</h3>

                            <!-- 현재 상태 배지 -->
                            <div style="display:inline-block; background:#fef3c7; border:1px solid #fbbf24; padding:8px 12px; border-radius:6px; margin-bottom:16px;">
                                <span style="font-size:12px; color:#92400e;">현재 상태: <b>${currentItem.reviewer_status}</b> | Revision: #${currentItem.latest_revision_number || 1}</span>
                            </div>

                            <textarea id="reviewNote" placeholder="수정 요청 사항을 구체적으로 적어주세요...">${currentItem.reviewer_note || ''}</textarea>

                            <div id="validationError" style="color: #ef4444; font-size: 13px; margin-bottom: 10px; display: none;"></div>

                            <!-- 버튼 그룹 -->
                            <div style="display:grid; gap:10px; margin-top:16px;">
                                <button class="btn btn-green" onclick="submitReview('approved')" style="display:flex; align-items:center; justify-content:center; gap:8px;">
                                    <span>✅</span>
                                    <div style="text-align:left; flex:1;">
                                        <div style="font-weight:bold;">Approve</div>
                                        <div style="font-size:11px; opacity:0.8;">마켓 전송 대기열로 이동 (최종 승인)</div>
                                    </div>
                                </button>

                                <button class="btn btn-blue" onclick="submitReview('needs_edit')" style="display:flex; align-items:center; justify-content:center; gap:8px;">
                                    <span>✏️</span>
                                    <div style="text-align:left; flex:1;">
                                        <div style="font-weight:bold;">Request Revision</div>
                                        <div style="font-size:11px; opacity:0.8;">위 메모를 AI에게 전달하여 재작성 요청 (Retry 가능)</div>
                                    </div>
                                </button>

                                <button class="btn btn-red" onclick="submitReview('rejected')" style="display:flex; align-items:center; justify-content:center; gap:8px;">
                                    <span>🚫</span>
                                    <div style="text-align:left; flex:1;">
                                        <div style="font-weight:bold;">Reject</div>
                                        <div style="font-size:11px; opacity:0.8;">영구 기각 (복구 불가)</div>
                                    </div>
                                </button>
                            </div>

                            ${currentItem.reviewer_status === 'needs_edit' ? `
                                <div style="margin-top:20px; padding:16px; background:#eff6ff; border:2px dashed #3b82f6; border-radius:8px;">
                                    <p style="margin:0 0 10px 0; font-weight:600; color:#1e40af;">
                                        💡 다음 단계: AI 재시도 실행
                                    </p>
                                    <p style="margin:0 0 12px 0; font-size:13px; color:#1e3a8a;">
                                        위에 작성한 리뷰 메모를 AI Agent에게 전달하여 상품 정보를 다시 생성합니다.
                                    </p>
                                    <button id="retryBtn" class="btn btn-blue" style="width:100%; background:#6366f1;" onclick="triggerRetry()">
                                        🚀 AI Retry with Note
                                    </button>
                                </div>
                            ` : ''}

                            ${currentItem.reviewer_status === 'approved' ? `
                                <div style="margin-top:20px; padding:16px; background:#f0fdf4; border:2px solid #86efac; border-radius:8px;">
                                    <p style="margin:0 0 10px 0; font-weight:600; color:#166534;">
                                        ✅ 승인 완료 - 데이터 다운로드
                                    </p>
                                    <div style="display:flex; gap:8px;">
                                        <button class="btn btn-blue" style="font-size:12px; background:#1f2937; flex:1;" onclick="downloadExport('/api/queue/${currentItem.review_id}/export/json', 'export_${currentItem.review_id}.json')">📄 JSON</button>
                                        <button class="btn btn-blue" style="font-size:12px; background:#4b5563; flex:1;" onclick="downloadExport('/api/queue/${currentItem.review_id}/export/csv', 'export_${currentItem.review_id}.csv')">📊 CSV</button>
                                    </div>
                                </div>
                            ` : ''}
                        </div>

                        <!-- Revision History -->
                        <div id="revisionHistory" style="margin-top:30px;">
                            <h3>Revision History</h3>
                            <div id="revisionsList">Loading history...</div>
                        </div>

                        <!-- 전체 JSON (접기 가능) -->
                        <details style="margin-top:30px;">
                            <summary style="cursor:pointer; font-weight:600; color:#3b82f6; font-size:14px; padding:12px; background:#f3f4f6; border-radius:6px;">
                                🔍 전체 JSON 데이터 보기 (개발자용)
                            </summary>
                            <pre style="margin-top:10px;">${JSON.stringify(currentItem.raw_agent_output, null, 2)}</pre>
                        </details>
                    `;
                    loadRevisions(id);
                } catch(e) {
                    document.getElementById('mainContent').innerHTML = `
                        <div style="text-align:center; padding:60px 20px; color:#ef4444;">
                            <div style="font-size:48px;">❌</div>
                            <h3 style="margin:16px 0 8px 0;">Failed to load item details</h3>
                            <p style="margin:0; font-size:14px; color:#6b7280;">Error: ${e.message || 'Unknown error'}</p>
                        </div>
                    `;
                }
            }

            async function downloadExport(url, filename) {
                try {
                    const res = await authenticatedFetch(url);
                    const blob = await res.blob();
                    const link = document.createElement('a');
                    link.href = window.URL.createObjectURL(blob);
                    link.download = filename;
                    link.click();
                } catch(e) {}
            }

            async function loadRevisions(id) {
                try {
                    const res = await authenticatedFetch(`/api/queue/${id}/revisions`);
                    const revs = await res.json();
                    const listEl = document.getElementById('revisionsList');
                    if (revs.length === 0) {
                        listEl.innerHTML = '<p style="color: #6b7280;">수정 이력이 없습니다.</p>';
                        return;
                    }
                    
                    listEl.innerHTML = revs.map(r => `
                        <div style="border: 1px solid #e5e7eb; padding: 10px; border-radius: 6px; margin-bottom: 10px; background: ${r.generation_status === 'completed' ? '#f0fdf4' : '#fef2f2'}">
                            <div style="font-weight: bold;">Revision ${r.revision_number} [${r.generation_status}]</div>
                            <div style="font-size: 12px; color: #4b5563;">Note: ${r.reviewer_note}</div>
                            <div style="font-size: 12px; color: #9ca3af;">Created: ${r.created_at}</div>
                            ${r.generation_status === 'completed' ? `<details style="font-size: 12px; margin-top: 5px;"><summary>View Output</summary><pre style="font-size: 10px;">${JSON.stringify(r.revised_agent_output, null, 2)}</pre></details>` : ''}
                        </div>
                    `).join('');
                } catch(e) {}
            }

            async function triggerRetry() {
                const btn = document.getElementById('retryBtn');
                btn.disabled = true;
                btn.innerText = '⌛ Validating & Retrying...';
                document.getElementById('validationError').style.display = 'none';

                try {
                    const res = await authenticatedFetch(`/api/queue/${currentItem.review_id}/retry`, { method: 'POST' });
                    if (res.ok) {
                        alert('Retry successful!');
                        loadDetail(currentItem.review_id);
                        loadItems();
                    } else {
                        const err = await res.json();
                        const errEl = document.getElementById('validationError');
                        errEl.innerText = 'Validation Error: ' + err.detail;
                        errEl.style.display = 'block';
                        btn.disabled = false;
                        btn.innerText = '🚀 Retry Agent with Note';
                    }
                } catch (e) {
                    btn.disabled = false;
                    btn.innerText = '🚀 Retry Agent with Note';
                }
            }

            async function submitReview(status) {
                const note = document.getElementById('reviewNote').value;
                const body = { reviewer_status: status, reviewer_note: note };
                
                try {
                    const res = await authenticatedFetch('/api/queue/' + currentItem.review_id, {
                        method: 'PATCH',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(body)
                    });
                    
                    if (res.ok) {
                        alert('Review submitted: ' + status);
                        loadItems();
                        document.getElementById('mainContent').innerHTML = '<h2>Item reviewed successfully.</h2>';
                    } else {
                        const err = await res.json();
                        alert('Error: ' + err.detail);
                    }
                } catch(e) {}
            }

            async function runHandoff() {
                if (!confirm('승인된 아이템의 최신 리비전을 기반으로 Handoff를 실행하시겠습니까?')) return;

                const btn = document.getElementById('handoffBtn');
                btn.disabled = true;
                btn.innerText = '⌛ Sending Handoff...';

                try {
                    const res = await authenticatedFetch('/api/handoff/run', { method: 'POST' });
                    const result = await res.json();

                    if (res.ok) {
                        let msg = `✅ Handoff ${result.overall_result}!\n`;
                        msg += `Count: ${result.count}\n`;
                        msg += `Mode: ${result.mode}\n`;
                        msg += `Slack: ${result.slack.status}\n`;
                        msg += `Email: ${result.email.status}`;
                        alert(msg);
                        loadHandoffStatus();
                    } else if (res.status === 409) {
                        alert('⚠️ Handoff Already In Progress\n\n' + result.detail);
                    } else {
                        alert('❌ Handoff Failed: ' + result.detail);
                    }
                } catch (e) {
                    alert('❌ Handoff Error: ' + e.message);
                } finally {
                    btn.disabled = false;
                    btn.innerText = '🚀 Run Handoff (Slack/Email)';
                }
            }

            async function loadHandoffStatus() {
                try {
                    const runsRes = await authenticatedFetch('/api/handoff/runs');
                    const runsData = await runsRes.json();
                    const el = document.getElementById('handoffStatus');

                    // Check if handoff is currently running
                    if (runsData.current_run) {
                        const currentRun = runsData.current_run;
                        el.innerHTML = `
                            <b style="color:#ef4444;">🔄 Handoff In Progress</b><br>
                            <b>Started:</b> ${currentRun.started_at.substring(11,19)}<br>
                            <b>Mode:</b> ${currentRun.mode}
                        `;
                        el.style.borderColor = '#fbbf24';
                        el.style.background = '#fffbeb';

                        // Disable handoff button
                        const btn = document.getElementById('handoffBtn');
                        btn.disabled = true;
                        btn.innerText = '⌛ Handoff Running...';

                        // Re-check after 3 seconds
                        setTimeout(loadHandoffStatus, 3000);
                        return;
                    }

                    // No current run, show last completed run
                    if (runsData.recent_runs.length === 0) {
                        el.innerHTML = 'No handoff history yet.';
                        return;
                    }

                    const last = runsData.recent_runs[0];
                    const resultColor = last.overall_result === 'success' || last.overall_result === 'success_log_only' ? '#166534' :
                                       last.overall_result === 'partial' ? '#d97706' :
                                       last.overall_result === 'no_op' ? '#6b7280' : '#991b1b';

                    el.innerHTML = `
                        <b>Last Run:</b> ${last.started_at.substring(11,19)}<br>
                        <b>Result:</b> <span style="color:${resultColor};">${last.overall_result}</span><br>
                        <b>Items:</b> ${last.item_count} | <b>Mode:</b> ${last.mode}<br>
                        <b>Slack:</b> ${last.slack_status} | <b>Email:</b> ${last.email_status}
                    `;
                    el.style.borderColor = '#fecaca';
                    el.style.background = '#fff';

                    // Re-enable handoff button
                    const btn = document.getElementById('handoffBtn');
                    btn.disabled = false;
                    btn.innerText = '🚀 Run Handoff (Slack/Email)';

                } catch(e) {
                    document.getElementById('handoffStatus').innerHTML = 'Auth required for status.';
                }
            }

            async function verifyChannels() {
                const statusEl = document.getElementById('verifyStatus');
                statusEl.style.display = 'block';
                statusEl.innerHTML = '⌛ Verifying Slack and Email...';

                try {
                    const res = await authenticatedFetch('/api/handoff/verify');
                    const result = await res.json();

                    let html = `<b>Mode:</b> ${result.mode}<br><br>`;

                    // Slack status
                    const slackIcon = result.slack.status === 'verified' ? '✅' :
                                     result.slack.status === 'failed' ? '❌' :
                                     result.slack.status === 'not_verified' ? '⚠️' : '❓';
                    html += `<b>${slackIcon} Slack:</b> ${result.slack.status}<br>`;
                    if (result.slack.message) html += `<span style="font-size:9px;">${result.slack.message}</span><br>`;
                    if (result.slack.error) html += `<span style="font-size:9px; color:#991b1b;">Error: ${result.slack.error}</span><br>`;

                    html += '<br>';

                    // Email status
                    const emailIcon = result.email.status === 'verified' ? '✅' :
                                     result.email.status === 'failed' ? '❌' :
                                     result.email.status === 'not_verified' ? '⚠️' : '❓';
                    html += `<b>${emailIcon} Email:</b> ${result.email.status}<br>`;
                    if (result.email.message) html += `<span style="font-size:9px;">${result.email.message}</span><br>`;
                    if (result.email.error) html += `<span style="font-size:9px; color:#991b1b;">Error: ${result.email.error}</span><br>`;

                    statusEl.innerHTML = html;
                } catch(e) {
                    statusEl.innerHTML = '❌ Verification failed: ' + e.message;
                }
            }

            async function loadStatusSummary() {
                try {
                    const res = await fetch('/api/stats');
                    const stats = await res.json();

                    const currentStatus = document.getElementById('statusFilter').value;

                    document.getElementById('statusSummary').innerHTML = `
                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px;">
                            <div style="padding:6px; background:${currentStatus === 'pending' ? '#dbeafe' : '#fff'}; border-radius:4px; text-align:center;">
                                <div style="font-size:18px; font-weight:bold; color:#3b82f6;">${stats.pending}</div>
                                <div style="font-size:10px;">Pending</div>
                            </div>
                            <div style="padding:6px; background:${currentStatus === 'approved' ? '#dcfce7' : '#fff'}; border-radius:4px; text-align:center;">
                                <div style="font-size:18px; font-weight:bold; color:#10b981;">${stats.approved}</div>
                                <div style="font-size:10px;">Approved</div>
                            </div>
                            <div style="padding:6px; background:${currentStatus === 'needs_edit' ? '#fef3c7' : '#fff'}; border-radius:4px; text-align:center;">
                                <div style="font-size:18px; font-weight:bold; color:#f59e0b;">${stats.needs_edit}</div>
                                <div style="font-size:10px;">Needs Edit</div>
                            </div>
                            <div style="padding:6px; background:${currentStatus === 'rejected' ? '#fee2e2' : '#fff'}; border-radius:4px; text-align:center;">
                                <div style="font-size:18px; font-weight:bold; color:#ef4444;">${stats.rejected}</div>
                                <div style="font-size:10px;">Rejected</div>
                            </div>
                        </div>
                        <div style="text-align:center; padding-top:8px; border-top:1px solid #e5e7eb;">
                            <b>Total:</b> ${stats.total}
                        </div>
                    `;
                } catch(e) {
                    document.getElementById('statusSummary').innerHTML = 'Stats unavailable.';
                }
            }

            // Init
            document.getElementById('adminToken').value = getToken();
            loadItems();
            loadHandoffStatus();
            loadStatusSummary();  // 통계 로드 추가
        </script>
    </body>
    </html>
        </script>
    </body>
    </html>
    """

# OLD ROUTE - Replaced with Template-based Agent Console (see line 1613)
# @app.get("/agents", response_class=HTMLResponse)
def agents_dashboard_old():
    """Multi-Agent Dashboard - 5개 에이전트 실시간 모니터링"""
    return """
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🤖 Multi-Agent Dashboard | Fortimove PM Agent</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #1f2937;
                min-height: 100vh;
                padding: 20px;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            .header {
                background: white;
                padding: 24px;
                border-radius: 12px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .header h1 {
                font-size: 28px;
                font-weight: 700;
                color: #111827;
            }
            .header .nav {
                display: flex;
                gap: 12px;
            }
            .header .nav a {
                padding: 10px 20px;
                background: #f3f4f6;
                border-radius: 6px;
                text-decoration: none;
                color: #4b5563;
                font-weight: 600;
                font-size: 14px;
                transition: 0.2s;
            }
            .header .nav a:hover {
                background: #e5e7eb;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 16px;
                margin-bottom: 20px;
            }
            .stat-card {
                background: white;
                padding: 20px;
                border-radius: 12px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                text-align: center;
            }
            .stat-card .number {
                font-size: 36px;
                font-weight: 700;
                margin-bottom: 8px;
            }
            .stat-card .label {
                font-size: 13px;
                color: #6b7280;
                font-weight: 600;
            }
            .agents-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
                gap: 20px;
                margin-bottom: 20px;
            }
            .agent-card {
                background: white;
                border-radius: 12px;
                padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                transition: 0.2s;
                position: relative;
                overflow: hidden;
            }
            .agent-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            }
            .agent-card .status-indicator {
                position: absolute;
                top: 20px;
                right: 20px;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                animation: pulse 2s infinite;
            }
            .agent-card.status-idle .status-indicator { background: #9ca3af; }
            .agent-card.status-running .status-indicator { background: #3b82f6; }
            .agent-card.status-completed .status-indicator { background: #10b981; }
            .agent-card.status-failed .status-indicator { background: #ef4444; }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            .agent-card h3 {
                font-size: 18px;
                margin-bottom: 8px;
                color: #111827;
                display: flex;
                align-items: center;
                gap: 8px;
            }
            .agent-card .status-text {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            .status-idle { background: #f3f4f6; color: #6b7280; }
            .status-running { background: #dbeafe; color: #1e40af; }
            .status-completed { background: #d1fae5; color: #065f46; }
            .status-failed { background: #fee2e2; color: #991b1b; }

            .agent-card .current-task {
                margin: 12px 0;
                padding: 12px;
                background: #f9fafb;
                border-radius: 6px;
                font-size: 13px;
                color: #374151;
                min-height: 60px;
            }
            .agent-card .stats-row {
                display: flex;
                justify-content: space-around;
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid #e5e7eb;
            }
            .agent-card .stat-item {
                text-align: center;
            }
            .agent-card .stat-item .number {
                font-size: 20px;
                font-weight: 700;
                color: #111827;
            }
            .agent-card .stat-item .label {
                font-size: 11px;
                color: #9ca3af;
                margin-top: 4px;
            }
            .workflow-section {
                background: white;
                border-radius: 12px;
                padding: 24px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }
            .workflow-section h2 {
                font-size: 20px;
                margin-bottom: 16px;
                color: #111827;
            }
            .workflow-list {
                display: flex;
                flex-direction: column;
                gap: 12px;
            }
            .workflow-item {
                padding: 16px;
                background: #f9fafb;
                border-radius: 8px;
                border-left: 4px solid #e5e7eb;
                display: flex;
                justify-content: space-between;
                align-items: center;
                transition: 0.2s;
                cursor: pointer;
            }
            .workflow-item:hover {
                background: #f3f4f6;
            }
            .workflow-item.completed { border-left-color: #10b981; }
            .workflow-item.failed { border-left-color: #ef4444; }
            .workflow-item.running { border-left-color: #3b82f6; }

            .workflow-item .info .id {
                font-size: 12px;
                color: #6b7280;
                font-family: monospace;
            }
            .workflow-item .info .task {
                font-size: 14px;
                color: #111827;
                font-weight: 600;
                margin-top: 4px;
            }
            .workflow-item .meta {
                text-align: right;
            }
            .workflow-item .meta .duration {
                font-size: 12px;
                color: #6b7280;
            }
            .workflow-item .meta .timestamp {
                font-size: 11px;
                color: #9ca3af;
                margin-top: 4px;
            }
            .refresh-btn {
                position: fixed;
                bottom: 30px;
                right: 30px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: #3b82f6;
                color: white;
                border: none;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
                transition: 0.2s;
            }
            .refresh-btn:hover {
                transform: scale(1.1);
                background: #2563eb;
            }
            .empty-state {
                text-align: center;
                padding: 40px;
                color: #9ca3af;
            }
            .empty-state .icon {
                font-size: 48px;
                margin-bottom: 12px;
                opacity: 0.3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <!-- Header -->
            <div class="header">
                <h1>🤖 Multi-Agent Dashboard</h1>
                <div class="nav">
                    <a href="/">승인 대기열</a>
                    <a href="/agents">에이전트 모니터</a>
                    <a href="/health" target="_blank">Health Check</a>
                </div>
            </div>

            <!-- Top Statistics -->
            <div class="stats-grid" id="topStats">
                <div class="stat-card">
                    <div class="number" style="color: #3b82f6;" id="runningCount">-</div>
                    <div class="label">실행 중</div>
                </div>
                <div class="stat-card">
                    <div class="number" style="color: #10b981;" id="completedCount">-</div>
                    <div class="label">완료</div>
                </div>
                <div class="stat-card">
                    <div class="number" style="color: #ef4444;" id="failedCount">-</div>
                    <div class="label">실패</div>
                </div>
                <div class="stat-card">
                    <div class="number" style="color: #6b7280;" id="totalWorkflows">-</div>
                    <div class="label">총 워크플로우</div>
                </div>
            </div>

            <!-- Agents Grid -->
            <div class="agents-grid" id="agentsGrid">
                <!-- Agents will be loaded here -->
            </div>

            <!-- Recent Workflows -->
            <div class="workflow-section">
                <h2>📋 최근 Workflow 실행 이력</h2>
                <div class="workflow-list" id="workflowList">
                    <!-- Workflows will be loaded here -->
                </div>
            </div>
        </div>

        <!-- Refresh Button -->
        <button class="refresh-btn" onclick="loadAll()" title="새로고침">🔄</button>

        <script>
            async function loadAgentStatus() {
                try {
                    const res = await fetch('/api/agents/status');
                    const data = await res.json();

                    const agentsGrid = document.getElementById('agentsGrid');
                    agentsGrid.innerHTML = '';

                    const agentOrder = ['pm', 'product_registration', 'cs', 'sourcing', 'pricing'];
                    const agentIcons = {
                        'pm': '👔',
                        'product_registration': '📦',
                        'cs': '💬',
                        'sourcing': '🔍',
                        'pricing': '💰'
                    };

                    agentOrder.forEach(agentKey => {
                        const agent = data.agents[agentKey];
                        if (!agent) return;

                        const card = document.createElement('div');
                        card.className = `agent-card status-${agent.status}`;

                        const currentTaskHTML = agent.current_task
                            ? `<strong>현재 작업:</strong> ${agent.current_task}`
                            : '<span style="color:#9ca3af;">대기 중...</span>';

                        card.innerHTML = `
                            <div class="status-indicator"></div>
                            <h3>
                                <span style="font-size:24px;">${agentIcons[agentKey]}</span>
                                ${agent.name}
                            </h3>
                            <span class="status-text status-${agent.status}">${agent.status}</span>

                            <div class="current-task">
                                ${currentTaskHTML}
                            </div>

                            <div class="stats-row">
                                <div class="stat-item">
                                    <div class="number">${agent.total_executions}</div>
                                    <div class="label">총 실행</div>
                                </div>
                                <div class="stat-item">
                                    <div class="number" style="color:#10b981;">${agent.success_count}</div>
                                    <div class="label">성공</div>
                                </div>
                                <div class="stat-item">
                                    <div class="number" style="color:#ef4444;">${agent.failure_count}</div>
                                    <div class="label">실패</div>
                                </div>
                            </div>

                            <div style="margin-top:12px; font-size:11px; color:#9ca3af; text-align:center;">
                                최근 업데이트: ${new Date(agent.last_updated).toLocaleString('ko-KR')}
                            </div>
                        `;

                        agentsGrid.appendChild(card);
                    });

                } catch (e) {
                    console.error('Failed to load agent status:', e);
                    document.getElementById('agentsGrid').innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>에이전트 상태를 불러올 수 없습니다</p></div>';
                }
            }

            async function loadStatistics() {
                try {
                    const res = await fetch('/api/agents/statistics');
                    const stats = await res.json();

                    document.getElementById('runningCount').textContent = stats.running_agents || 0;
                    document.getElementById('completedCount').textContent = stats.completed_workflows || 0;
                    document.getElementById('failedCount').textContent = stats.failed_workflows || 0;
                    document.getElementById('totalWorkflows').textContent = stats.total_workflows || 0;

                } catch (e) {
                    console.error('Failed to load statistics:', e);
                }
            }

            async function loadWorkflowHistory() {
                try {
                    const res = await fetch('/api/workflows/history?limit=10');
                    const workflows = await res.json();

                    const workflowList = document.getElementById('workflowList');

                    if (workflows.length === 0) {
                        workflowList.innerHTML = '<div class="empty-state"><div class="icon">📭</div><p>아직 실행된 워크플로우가 없습니다</p></div>';
                        return;
                    }

                    workflowList.innerHTML = '';

                    workflows.forEach(workflow => {
                        const item = document.createElement('div');
                        item.className = `workflow-item ${workflow.status}`;

                        const createdAt = new Date(workflow.created_at).toLocaleString('ko-KR');
                        const duration = workflow.duration_seconds.toFixed(1);

                        item.innerHTML = `
                            <div class="info">
                                <div class="id">${workflow.workflow_id}</div>
                                <div class="task">${workflow.task_type}</div>
                            </div>
                            <div class="meta">
                                <div class="duration">${duration}초</div>
                                <div class="timestamp">${createdAt}</div>
                            </div>
                        `;

                        item.onclick = () => {
                            alert(`Workflow ID: ${workflow.workflow_id}\n\nStatus: ${workflow.status}\nSteps: ${workflow.steps.length}개\nDuration: ${duration}초\n\n상세 UI는 추후 구현 예정입니다.`);
                        };

                        workflowList.appendChild(item);
                    });

                } catch (e) {
                    console.error('Failed to load workflow history:', e);
                    document.getElementById('workflowList').innerHTML = '<div class="empty-state"><div class="icon">⚠️</div><p>워크플로우 이력을 불러올 수 없습니다</p></div>';
                }
            }

            async function loadAll() {
                await Promise.all([
                    loadAgentStatus(),
                    loadStatistics(),
                    loadWorkflowHistory()
                ]);
            }

            // Auto-refresh every 5 seconds
            setInterval(loadAll, 5000);

            // Initial load
            loadAll();
        </script>
    </body>
    </html>
    """


# ============================================================
# Phase 4 UI Routes
# ============================================================

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Mount static files
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Setup templates
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Phase 4 Review Console API Router
from review_console_api import router as review_console_router
app.include_router(review_console_router)

# Phase 1 Content Generation API Router
from content_generation_api import router as content_generation_router
app.include_router(content_generation_router)


@app.get("/", response_class=HTMLResponse)
async def business_dashboard_page(request: Request):
    """Business Dashboard - 대표용 메인 대시보드"""
    return templates.TemplateResponse(request=request, name="business_dashboard.html", context={})


@app.get("/agents", response_class=HTMLResponse)
async def agent_console_page(request: Request):
    """Agent Console - 기술 관리자용 대시보드"""
    return templates.TemplateResponse(request=request, name="agent_console.html", context={})


@app.get("/review/list", response_class=HTMLResponse)
async def review_list_page(request: Request):
    """Review list page"""
    return templates.TemplateResponse(request=request, name="review_list.html", context={})


@app.get("/review/detail/{review_id}", response_class=HTMLResponse)
async def review_detail_page(request: Request, review_id: str):
    """Review detail page - Phase 1 상품 기획 워크벤치"""
    return templates.TemplateResponse(
        request=request,
        name="review_detail_phase1.html",
        context={"review_id": review_id}
    )

@app.get("/review/detail-legacy/{review_id}", response_class=HTMLResponse)
async def review_detail_legacy_page(request: Request, review_id: str):
    """Legacy review detail page (backup)"""
    return templates.TemplateResponse(
        request=request,
        name="review_detail.html",
        context={"review_id": review_id}
    )


