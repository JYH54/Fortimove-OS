from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import csv
import io

from datetime import datetime
from approval_queue import ApprovalQueueManager
from handoff_service import HandoffService

from fastapi.security import APIKeyHeader
from fastapi import Security, Depends

app = FastAPI(title="Fortimove Approval UI MVP")
handoff_service = HandoffService()

API_KEY_NAME = "X-API-TOKEN"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_admin_token(api_key: str = Security(api_key_header)):
    import os
    admin_token = os.getenv("ADMIN_TOKEN")
    allow_noauth = os.getenv("ALLOW_LOCAL_NOAUTH") == "true"
    
    if not admin_token and not allow_noauth:
        raise HTTPException(status_code=401, detail="ADMIN_TOKEN not configured on server. Access denied.")
    
    if allow_noauth:
        return True
        
    if api_key != admin_token:
        raise HTTPException(status_code=401, detail="Invalid or missing API Token")
    return True

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

class ReviewUpdateRequest(BaseModel):
    reviewer_status: str
    reviewer_note: Optional[str] = ""

# Dependency injection for easy testing/overriding
def get_aq() -> ApprovalQueueManager:
    return ApprovalQueueManager()

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

@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Approval Queue MVP</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; height: 100vh; margin: 0; background: #f9fafb; color: #111827;}
            .sidebar { width: 350px; border-right: 1px solid #e5e7eb; padding: 20px; overflow-y: auto; background: #fff;}
            .main { flex: 1; padding: 20px; overflow-y: auto; }
            .item-card { padding: 12px; border: 1px solid #e5e7eb; border-radius: 8px; margin-bottom: 12px; cursor: pointer; transition: 0.2s; }
            .item-card:hover { border-color: #3b82f6; background: #eff6ff;}
            .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
            .badge.hold { background: #fee2e2; color: #991b1b; }
            .badge.ready { background: #dcfce3; color: #166534; }
            pre { background: #1f2937; color: #e5e7eb; padding: 16px; border-radius: 8px; overflow-x: auto; font-size: 13px;}
            .btn { cursor: pointer; padding: 8px 16px; border: none; border-radius: 6px; font-weight: 600; color: white;}
            .btn-blue { background: #3b82f6; }
            .btn-green { background: #10b981; }
            .btn-red { background: #ef4444; }
            .actions-bar { margin-top: 20px; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px; background: white;}
            .batch-box { margin-top: 25px; padding: 15px; background: #fdf2f2; border: 1px solid #fecaca; border-radius: 8px; font-size: 13px;}
            .settings-box { border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 20px; font-size: 12px; color: #4b5563; }
            .status-badge { font-size: 10px; padding: 2px 4px; border-radius: 3px; background: #e5e7eb; margin-left: 5px; }
            textarea { width: 100%; height: 80px; margin-bottom: 10px; padding: 8px; border-radius: 4px; border: 1px solid #d1d5db;}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2 style="margin:0;">Queue</h2>
                <a href="/health" target="_blank" style="font-size: 10px; color: #10b981; text-decoration: none;">● System Healthy</a>
            </div>
            
            <select id="statusFilter" onchange="loadItems()" style="width:100%; padding:8px; margin: 15px 0;">
                <option value="pending" selected>Pending</option>
                <option value="approved">Approved</option>
                <option value="needs_edit">Needs Edit</option>
                <option value="rejected">Rejected</option>
            </select>
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
                const token = document.getElementById('adminToken').value;
                localStorage.setItem('admin_token', token);
                alert('Token saved to localStorage!');
                loadItems();
                loadHandoffStatus();
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
                    document.getElementById('itemList').innerHTML = '<div style="color:#ef4444; font-size:12px;">Failed to load items. Check token.</div>';
                }
            }

            async function loadDetail(id) {
                try {
                    const res = await authenticatedFetch('/api/queue/' + id);
                    currentItem = await res.json();
                    
                    const mainEl = document.getElementById('mainContent');
                    
                    mainEl.innerHTML = `
                        <h2>${currentItem.source_title}</h2>
                        <p><b>Status:</b> ${currentItem.registration_status} | <b>Human Review:</b> ${currentItem.needs_human_review}</p>
                        <p><b>Reasons:</b> ${currentItem.hold_reason || currentItem.reject_reason || 'None'}</p>
                        <hr>
                        <h3>Raw Agent Output (Immutable)</h3>
                        <pre>${JSON.stringify(currentItem.raw_agent_output, null, 2)}</pre>
                        
                        <div class="actions-bar">
                            <h3>Review Decision</h3>
                            <p>Current Review Status: <b>${currentItem.reviewer_status}</b></p>
                            <p style="font-size: 12px; color: #6b7280;">Latest Rev: #${currentItem.latest_revision_number || 1} (${currentItem.latest_registration_title_ko || 'N/A'})</p>
                            
                            <textarea id="reviewNote" placeholder="수정 요청 사항을 구체적으로 적어주세요...">${currentItem.reviewer_note || ''}</textarea><br>
                            
                            <div id="validationError" style="color: #ef4444; font-size: 13px; margin-bottom: 10px; display: none;"></div>

                            <button class="btn btn-green" onclick="submitReview('approved')">Approve (마켓전송대기)</button>
                            <button class="btn btn-blue" onclick="submitReview('needs_edit')">Needs Edit (수정재요청)</button>
                            <button class="btn btn-red" onclick="submitReview('rejected')">Reject (기각)</button>
                            
                            ${currentItem.reviewer_status === 'needs_edit' ? 
                                `<button id="retryBtn" class="btn btn-blue" style="margin-top:10px; background:#6366f1;" onclick="triggerRetry()">🚀 Retry Agent with Note</button>` 
                                : ''
                            }

                            ${currentItem.reviewer_status === 'approved' ? 
                                `<div style="margin-top: 15px; padding-top: 15px; border-top: 1px dashed #e5e7eb;">
                                    <p style="font-size: 13px; font-weight: bold; color: #166534;">✅ Approved Item Download (Latest Revision)</p>
                                    <button class="btn btn-blue" style="font-size:12px; background:#1f2937;" onclick="downloadExport('/api/queue/${currentItem.review_id}/export/json', 'export_${currentItem.review_id}.json')">Export JSON</button>
                                    <button class="btn btn-blue" style="font-size:12px; background:#4b5563;" onclick="downloadExport('/api/queue/${currentItem.review_id}/export/csv', 'export_${currentItem.review_id}.csv')">Export CSV</button>
                                 </div>` 
                                : ''
                            }
                        </div>

                        <div id="revisionHistory" style="margin-top: 30px;">
                            <h3>Revision History</h3>
                            <div id="revisionsList">Loading history...</div>
                        </div>
                    `;
                    loadRevisions(id);
                } catch(e) {}
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

            // Init
            document.getElementById('adminToken').value = getToken();
            loadItems();
            loadHandoffStatus();
        </script>
    </body>
    </html>
        </script>
    </body>
    </html>
    """
