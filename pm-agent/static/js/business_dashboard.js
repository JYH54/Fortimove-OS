/**
 * Business Dashboard - 대표용 운영 대시보드
 */

let currentWorkflowId = null;

// 초기 로드
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardStats();
    loadRecentTasks();
    setInterval(loadDashboardStats, 30000); // 30초마다 갱신
});

async function loadDashboardStats() {
    try {
        // 승인 대기열 통계 (Phase 4 API 사용)
        const statsResponse = await fetch('/api/stats');
        const stats = await statsResponse.json();

        // Phase 4 Review 목록 조회 (오늘 분석된 상품 수)
        const reviewResponse = await fetch('/api/phase4/review/list/all?limit=1000');
        const reviewData = await reviewResponse.json();

        // 오늘 날짜 기준 필터링
        const today = new Date().toISOString().split('T')[0];
        const todayItems = (reviewData.items || []).filter(item => {
            const createdDate = item.created_at ? item.created_at.split('T')[0] : '';
            return createdDate === today;
        });

        document.getElementById('todayAnalyzed').textContent = todayItems.length;

        // 전일 대비 계산 (어제 데이터와 비교)
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const yesterdayStr = yesterday.toISOString().split('T')[0];
        const yesterdayItems = (reviewData.items || []).filter(item => {
            const createdDate = item.created_at ? item.created_at.split('T')[0] : '';
            return createdDate === yesterdayStr;
        });

        const change = yesterdayItems.length > 0
            ? Math.round(((todayItems.length - yesterdayItems.length) / yesterdayItems.length) * 100)
            : 0;
        document.getElementById('analyzedChange').textContent =
            (change > 0 ? '+' : '') + change + '%';

        // 승인 대기 (under_review 상태)
        const pendingItems = (reviewData.items || []).filter(item =>
            item.review_status === 'under_review' || item.review_status === 'draft'
        );
        document.getElementById('pendingApproval').textContent = pendingItems.length;

        // 등록 완료 (approved_for_export, approved_for_upload)
        const approvedItems = (reviewData.items || []).filter(item =>
            item.review_status === 'approved_for_export' || item.review_status === 'approved_for_upload'
        );
        document.getElementById('registered').textContent = approvedItems.length;

        // 예상 수익 계산 (generated_price 필드 사용)
        let totalRevenue = 0;
        let totalMargin = 0;
        let itemsWithPrice = 0;

        approvedItems.forEach(item => {
            const price = parseFloat(item.generated_price || 0);
            if (price > 0) {
                totalRevenue += price;
                itemsWithPrice++;
                // 평균 마진율 40% 가정 (실제 데이터가 있다면 사용)
                totalMargin += 0.40;
            }
        });

        const avgMarginRate = itemsWithPrice > 0 ? (totalMargin / itemsWithPrice) * 100 : 0;

        document.getElementById('expectedRevenue').textContent =
            '₩' + Math.round(totalRevenue).toLocaleString();
        document.getElementById('avgMargin').textContent = avgMarginRate.toFixed(1);
        document.getElementById('revenueDetail').textContent =
            `${approvedItems.length}개 상품`;

        // 마지막 업데이트 시간
        document.getElementById('lastUpdate').textContent =
            new Date().toLocaleTimeString('ko-KR');

    } catch (error) {
        console.error('통계 로드 실패:', error);
        // 에러 시에도 UI가 깨지지 않도록 기본값 설정
        document.getElementById('todayAnalyzed').textContent = '0';
        document.getElementById('pendingApproval').textContent = '0';
        document.getElementById('registered').textContent = '0';
        document.getElementById('expectedRevenue').textContent = '₩0';
    }
}

async function loadRecentTasks() {
    try {
        const response = await fetch('/api/workflows/history?limit=5');
        const history = await response.json();

        const taskList = document.getElementById('recentTasks');

        if (!history || history.length === 0) {
            taskList.innerHTML = `
                <li class="task-item">
                    <small class="text-muted">아직 실행된 작업이 없습니다</small>
                </li>
            `;
            return;
        }

        taskList.innerHTML = history.map(task => {
            const statusBadge = getStatusBadge(task.status);
            const timeAgo = getTimeAgo(task.timestamp);

            return `
                <li class="task-item">
                    <div>
                        <div class="fw-bold" style="font-size: 0.9rem;">${task.task_type}</div>
                        <small class="text-muted">${timeAgo}</small>
                    </div>
                    <span class="badge-custom ${statusBadge.class}">${statusBadge.text}</span>
                </li>
            `;
        }).join('');

    } catch (error) {
        console.error('최근 작업 로드 실패:', error);
    }
}

function getStatusBadge(status) {
    const badges = {
        'pending': { class: 'badge-pending', text: '대기중' },
        'running': { class: 'badge-running', text: '진행중' },
        'completed': { class: 'badge-success', text: '완료' },
        'failed': { class: 'badge-failed', text: '실패' }
    };
    return badges[status] || badges['pending'];
}

function getTimeAgo(timestamp) {
    if (!timestamp) return '방금 전';

    const now = new Date();
    const past = new Date(timestamp);
    const diffMs = now - past;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return '방금 전';
    if (diffMins < 60) return `${diffMins}분 전`;

    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}시간 전`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}일 전`;
}

// ============================================================
// 워크플로우 실행
// ============================================================

async function startSourcingWorkflow() {
    const url = prompt('타오바오/1688 상품 URL을 입력하세요:', 'https://item.taobao.com/item.htm?id=');

    if (!url || url === 'https://item.taobao.com/item.htm?id=') {
        return;
    }

    showLoadingModal('상품 분석 중...', '소싱 가능성, 가격, 마진을 계산하고 있습니다');

    try {
        // 통합 워크플로우 실행: 소싱 → 가격 → 마진
        const response = await fetch('/api/workflows/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workflow_name: 'quick_sourcing_check',
                user_input: {
                    source_url: url,
                    source_title: '분석 대상 상품',
                    market: 'korea'
                },
                save_to_queue: true
            })
        });

        const result = await response.json();

        if (result.status === 'completed') {
            showSuccessResult('소싱 검토 완료', result);
        } else {
            showErrorResult('분석 실패', result.error || '알 수 없는 오류');
        }

        // 통계 갱신
        loadDashboardStats();
        loadRecentTasks();

    } catch (error) {
        showErrorResult('실행 오류', error.message);
    }
}

async function startRegistrationWorkflow() {
    const title = prompt('상품명을 입력하세요:', '');

    if (!title) {
        return;
    }

    showLoadingModal('등록 데이터 생성 중...', '채널별 콘텐츠와 이미지를 준비하고 있습니다');

    try {
        // 등록 워크플로우: 콘텐츠 생성 → 이미지 처리 → 옵션 정리
        const response = await fetch('/api/agents/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent: 'content',
                input: {
                    product_name: title,
                    content_type: 'product_page',
                    compliance_mode: true
                },
                save_to_queue: true
            })
        });

        const result = await response.json();

        if (result.status === 'completed') {
            showSuccessResult('등록 데이터 생성 완료', result);
        } else {
            showErrorResult('생성 실패', result.error || '알 수 없는 오류');
        }

        loadDashboardStats();
        loadRecentTasks();

    } catch (error) {
        showErrorResult('실행 오류', error.message);
    }
}

async function startCSWorkflow() {
    const message = prompt('고객 문의 내용을 입력하세요:', '');

    if (!message) {
        return;
    }

    showLoadingModal('답변 생성 중...', '고객 문의를 분석하고 답변 템플릿을 생성합니다');

    try {
        const response = await fetch('/api/agents/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent: 'cs',
                input: {
                    inquiry_type: '기타',
                    customer_message: message
                },
                save_to_queue: false
            })
        });

        const result = await response.json();

        if (result.status === 'completed') {
            showSuccessResult('CS 답변 생성 완료', result);
        } else {
            showErrorResult('생성 실패', result.error || '알 수 없는 오류');
        }

        loadRecentTasks();

    } catch (error) {
        showErrorResult('실행 오류', error.message);
    }
}

// ============================================================
// 빠른 작업
// ============================================================

function quickAction(action) {
    switch(action) {
        case 'check_daily_scout':
            window.location.href = 'http://localhost:8050';
            break;
        case 'view_approval_queue':
            window.location.href = '/review/list';
            break;
        case 'export_products':
            exportApprovedProducts();
            break;
    }
}

async function exportApprovedProducts() {
    try {
        const response = await fetch('/api/phase4/review/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                review_ids: [],  // 빈 배열 = 모든 승인된 항목
                channel: 'naver',
                exported_by: 'dashboard'
            })
        });

        const result = await response.json();

        if (result.csv_data) {
            // CSV 다운로드
            const blob = new Blob([result.csv_data], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = result.filename || 'products.csv';
            link.click();

            alert(`✅ ${result.row_count}개 상품을 내보냈습니다`);
        }

    } catch (error) {
        alert('내보내기 실패: ' + error.message);
    }
}

// 이력 보기 함수들
function viewSourcingHistory() {
    window.location.href = '/review/list';
}

function viewRegistrationQueue() {
    window.location.href = '/review/list';
}

function viewCSHistory() {
    window.location.href = '/review/list';
}

// ============================================================
// 모달 관리
// ============================================================

function showLoadingModal(title, message) {
    const modal = document.getElementById('resultModal');
    const titleEl = document.getElementById('resultTitle');
    const bodyEl = document.getElementById('resultBody');

    titleEl.textContent = title;
    bodyEl.innerHTML = `
        <div class="text-center py-4">
            <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;">
                <span class="visually-hidden">Loading...</span>
            </div>
            <h5 class="mb-2">${message}</h5>
            <p class="text-muted">잠시만 기다려주세요...</p>
        </div>
    `;

    modal.classList.add('show');
}

function showSuccessResult(title, result) {
    const modal = document.getElementById('resultModal');
    const titleEl = document.getElementById('resultTitle');
    const bodyEl = document.getElementById('resultBody');

    titleEl.textContent = '✅ ' + title;

    let detailsHtml = '';

    if (result.result) {
        const data = result.result;

        // 소싱 검토 결과
        if (data.sourcing_decision || data.final_price) {
            detailsHtml = `
                <div class="alert alert-success mb-3">
                    <h6 class="mb-2">분석 완료!</h6>
                    <p class="mb-0">승인 대기열에 저장되었습니다. "승인 대기열" 메뉴에서 확인하세요.</p>
                </div>

                ${data.sourcing_decision ? `
                    <div class="mb-3">
                        <strong>판정:</strong> ${data.sourcing_decision}
                    </div>
                ` : ''}

                ${data.final_price ? `
                    <div class="mb-3">
                        <strong>판매가:</strong> ₩${data.final_price.toLocaleString()}
                    </div>
                ` : ''}

                ${data.margin_rate ? `
                    <div class="mb-3">
                        <strong>마진율:</strong> ${(data.margin_rate * 100).toFixed(1)}%
                    </div>
                ` : ''}

                <div class="d-flex gap-2 mt-4">
                    <button class="btn btn-primary" onclick="window.location.href='/review/list'">
                        승인 대기열로 이동
                    </button>
                    <button class="btn btn-secondary" onclick="closeResultModal()">
                        닫기
                    </button>
                </div>
            `;
        }
        // 콘텐츠 생성 결과
        else if (data.seo_title || data.generated_naver_title) {
            detailsHtml = `
                <div class="alert alert-success mb-3">
                    <h6 class="mb-2">콘텐츠 생성 완료!</h6>
                </div>

                ${data.seo_title ? `
                    <div class="mb-3">
                        <strong>네이버 제목:</strong><br>
                        <div class="bg-light p-2 rounded">${data.seo_title}</div>
                    </div>
                ` : ''}

                ${data.generated_naver_title ? `
                    <div class="mb-3">
                        <strong>생성된 제목:</strong><br>
                        <div class="bg-light p-2 rounded">${data.generated_naver_title}</div>
                    </div>
                ` : ''}

                <div class="d-flex gap-2 mt-4">
                    <button class="btn btn-primary" onclick="window.location.href='/review/list'">
                        등록 대기열로 이동
                    </button>
                    <button class="btn btn-secondary" onclick="closeResultModal()">
                        닫기
                    </button>
                </div>
            `;
        }
        // 일반 결과
        else {
            detailsHtml = `
                <div class="alert alert-success mb-3">
                    <p class="mb-0">작업이 완료되었습니다.</p>
                </div>
                <details>
                    <summary class="btn btn-sm btn-outline-secondary mb-3">상세 결과 보기</summary>
                    <pre class="bg-light p-3 rounded" style="font-size: 0.85em; max-height: 300px; overflow-y: auto;">${JSON.stringify(result.result, null, 2)}</pre>
                </details>
                <button class="btn btn-secondary" onclick="closeResultModal()">닫기</button>
            `;
        }
    } else {
        detailsHtml = `
            <div class="alert alert-success">작업이 완료되었습니다.</div>
            <button class="btn btn-secondary" onclick="closeResultModal()">닫기</button>
        `;
    }

    bodyEl.innerHTML = detailsHtml;
    modal.classList.add('show');
}

function showErrorResult(title, message) {
    const modal = document.getElementById('resultModal');
    const titleEl = document.getElementById('resultTitle');
    const bodyEl = document.getElementById('resultBody');

    titleEl.textContent = '❌ ' + title;
    bodyEl.innerHTML = `
        <div class="alert alert-danger">
            <h6 class="mb-2">오류가 발생했습니다</h6>
            <p class="mb-0">${message}</p>
        </div>
        <button class="btn btn-secondary" onclick="closeResultModal()">닫기</button>
    `;

    modal.classList.add('show');
}

function closeResultModal() {
    const modal = document.getElementById('resultModal');
    modal.classList.remove('show');
}

// 모달 외부 클릭 시 닫기
document.getElementById('resultModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'resultModal') {
        closeResultModal();
    }
});
