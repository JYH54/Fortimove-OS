/**
 * Agent Console - 개별 에이전트 실행 및 모니터링
 */

let currentAgentId = null;

// Agent 한글명 및 설명
const AGENT_DISPLAY_INFO = {
    sourcing: {
        team_name: '소싱팀',
        description: '타오바오/1688 상품의 수입 가능성, KC인증 필요 여부, 리스크를 자동 판단',
        success_means: '수입 가능 판정 (통과/보류/거부)',
        test_description: '소싱 URL을 입력하면 해당 상품의 수입 리스크를 분석합니다'
    },
    pricing: {
        team_name: '가격팀',
        description: '소싱가 기준으로 물류비, 관세, 마진을 계산해 최종 판매가 산출',
        success_means: '판매가 계산 완료',
        test_description: '소싱가와 무게를 입력하면 판매가를 계산합니다'
    },
    content: {
        team_name: '콘텐츠팀',
        description: '네이버/쿠팡 채널별 상품 제목, 설명, 키워드를 AI로 생성',
        success_means: '채널별 콘텐츠 생성 완료',
        test_description: '상품명을 입력하면 판매 채널별 콘텐츠를 생성합니다'
    },
    product_registration: {
        team_name: '상품등록팀',
        description: '상품명, 옵션, 카테고리를 분석해 등록 데이터를 준비',
        success_means: '등록 데이터 생성 완료',
        test_description: '상품 정보를 입력하면 등록에 필요한 데이터를 생성합니다'
    },
    cs: {
        team_name: 'CS팀',
        description: '고객 문의 유형을 분석하고 답변 템플릿을 생성',
        success_means: 'CS 답변 생성 완료',
        test_description: '고객 문의를 입력하면 답변 템플릿을 생성합니다'
    },
    pm: {
        team_name: 'PM팀',
        description: '업무 우선순위를 판단하고 다음 액션을 제안',
        success_means: '업무 우선순위 판단 완료',
        test_description: '업무 상황을 입력하면 우선순위와 액션을 제안합니다'
    },
    image_localization: {
        team_name: '이미지팀',
        description: '상품 이미지의 중국어 텍스트를 감지하고 한글로 변환',
        success_means: '이미지 현지화 완료',
        test_description: '이미지 URL을 입력하면 텍스트를 한글로 변환합니다'
    },
    margin_check: {
        team_name: '마진검수팀',
        description: '원가 대비 판매가의 마진율을 계산하고 수익성을 검토',
        success_means: '마진율 계산 완료',
        test_description: '원가와 판매가를 입력하면 마진율을 계산합니다'
    },
    daily_scout_status: {
        team_name: 'Daily Scout 모니터',
        description: 'Daily Scout 크롤러의 상태를 모니터링',
        success_means: '상태 확인 완료',
        test_description: 'Daily Scout의 실행 상태를 확인합니다'
    }
};

// Agent Input Schemas
const AGENT_INPUT_SCHEMAS = {
    sourcing: {
        fields: [
            { name: 'source_url', label: '소싱 URL', type: 'text', required: true, placeholder: 'https://item.taobao.com/item.htm?id=...' },
            { name: 'source_title', label: '상품 제목', type: 'text', required: false },
            { name: 'source_description', label: '상품 설명', type: 'textarea', required: false },
            { name: 'source_price_cny', label: '매입가 (위안)', type: 'number', required: false },
            { name: 'market', label: '타겟 시장', type: 'text', required: false, placeholder: 'korea' }
        ]
    },
    pricing: {
        fields: [
            { name: 'source_price_cny', label: '소싱가 (위안)', type: 'number', required: true },
            { name: 'category', label: '카테고리', type: 'select', required: false,
              options: ['wellness', 'supplement', 'beauty', 'healthcare', 'general'] },
            { name: 'weight_kg', label: '무게 (kg)', type: 'number', required: false },
            { name: 'product_name', label: '상품명', type: 'text', required: false }
        ]
    },
    content: {
        fields: [
            { name: 'product_name', label: '상품명', type: 'text', required: true },
            { name: 'product_category', label: '카테고리', type: 'text', required: false },
            { name: 'key_features', label: '주요 특징 (쉼표 구분)', type: 'text', required: false },
            { name: 'price', label: '판매가', type: 'number', required: false },
            { name: 'content_type', label: '콘텐츠 타입', type: 'select', required: false,
              options: ['product_page', 'sns', 'blog', 'email'] },
            { name: 'compliance_mode', label: '컴플라이언스 모드', type: 'checkbox', required: false }
        ]
    },
    product_registration: {
        fields: [
            { name: 'source_title', label: '소싱 제목', type: 'text', required: true },
            { name: 'source_options', label: '옵션 (쉼표 구분)', type: 'text', required: false },
            { name: 'source_price', label: '소싱가', type: 'number', required: false }
        ]
    },
    cs: {
        fields: [
            { name: 'inquiry_type', label: '문의 유형', type: 'select', required: true,
              options: ['배송', '반품/교환', '결제', '상품문의', '기타'] },
            { name: 'customer_message', label: '고객 메시지', type: 'textarea', required: true },
            { name: 'order_id', label: '주문번호', type: 'text', required: false }
        ]
    },
    pm: {
        fields: [
            { name: 'task_type', label: '업무 유형', type: 'select', required: true,
              options: ['상품기획', '소싱검토', '가격검수', '등록승인', '기타'] },
            { name: 'context', label: '상황', type: 'textarea', required: true }
        ]
    }
};

async function loadAgentStatus() {
    try {
        const response = await fetch('/api/agents/status');
        const data = await response.json();

        // Update stats
        const agents = Object.values(data.agents);
        document.getElementById('totalAgents').textContent = agents.length;

        let totalExec = 0, totalSuccess = 0, totalFail = 0;
        agents.forEach(agent => {
            totalExec += agent.total_executions || 0;
            totalSuccess += agent.success_count || 0;
            totalFail += agent.failure_count || 0;
        });

        document.getElementById('totalExecutions').textContent = totalExec;
        document.getElementById('totalSuccess').textContent = totalSuccess;
        document.getElementById('totalFailures').textContent = totalFail;

        // Render agent cards
        renderAgentCards(data.agents);

    } catch (error) {
        console.error('Failed to load agent status:', error);
        showError('에이전트 상태 로드 실패');
    }
}

function renderAgentCards(agents) {
    const container = document.getElementById('agentContainer');
    container.innerHTML = '';

    Object.entries(agents).forEach(([agentId, agentData]) => {
        const successRate = agentData.total_executions > 0
            ? Math.round((agentData.success_count / agentData.total_executions) * 100)
            : 0;

        const statusClass = agentData.status === 'idle' ? 'status-idle' :
                          agentData.status === 'running' ? 'status-running' : 'status-error';

        const statusText = agentData.status === 'idle' ? '대기중' :
                          agentData.status === 'running' ? '실행중' : '에러';

        // Get display info
        const displayInfo = AGENT_DISPLAY_INFO[agentId] || {
            team_name: agentData.name,
            description: '에이전트 설명 없음',
            success_means: '작업 완료',
            test_description: '테스트 실행 가능'
        };

        const card = `
            <div class="col-md-6 col-lg-4">
                <div class="agent-card">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <h5 class="mb-0">${displayInfo.team_name}</h5>
                            <small class="text-muted">ID: ${agentId}</small>
                        </div>
                        <span class="agent-status ${statusClass}">${statusText}</span>
                    </div>

                    <p class="text-muted small mb-3" style="font-size: 0.85em; line-height: 1.4;">
                        ${displayInfo.description}
                    </p>

                    <div class="row text-center mb-2" style="background: #f8f9fa; padding: 10px; border-radius: 6px;">
                        <div class="col-4">
                            <small class="text-muted d-block" style="font-size: 0.75em;">총 실행</small>
                            <div class="fw-bold">${agentData.total_executions || 0}회</div>
                        </div>
                        <div class="col-4" style="cursor: pointer;" onclick="showSuccessDetail('${agentId}', '${displayInfo.team_name}', '${displayInfo.success_means}', ${agentData.success_count || 0})">
                            <small class="text-muted d-block" style="font-size: 0.75em;">✅ 성공</small>
                            <div class="fw-bold text-success">${agentData.success_count || 0}회</div>
                            <small style="font-size: 0.7em; color: #10b981;">클릭하여 상세보기</small>
                        </div>
                        <div class="col-4" style="cursor: pointer;" onclick="showFailureDetail('${agentId}', '${displayInfo.team_name}', ${agentData.failure_count || 0})">
                            <small class="text-muted d-block" style="font-size: 0.75em;">❌ 실패</small>
                            <div class="fw-bold text-danger">${agentData.failure_count || 0}회</div>
                            <small style="font-size: 0.7em; color: #ef4444;">클릭하여 상세보기</small>
                        </div>
                    </div>

                    ${agentData.total_executions > 0 ? `
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-success" style="width: ${successRate}%"></div>
                        </div>
                        <small class="text-muted">성공률: ${successRate}%</small>
                    ` : `
                        <small class="text-muted">아직 실행된 적이 없습니다</small>
                    `}

                    <button class="btn btn-primary execute-btn" onclick="openExecuteModal('${agentId}', '${displayInfo.team_name}')">
                        🧪 테스트 실행
                    </button>
                    <small class="d-block mt-2 text-muted" style="font-size: 0.75em;">
                        ${displayInfo.test_description}
                    </small>

                    <div id="result-${agentId}" class="result-box"></div>
                </div>
            </div>
        `;

        container.innerHTML += card;
    });
}

function showSuccessDetail(agentId, teamName, successMeans, count) {
    const modal = `
        <div class="modal fade" id="successDetailModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-success text-white">
                        <h5 class="modal-title">✅ ${teamName} - 성공 상세</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <h6 class="mb-3">"성공"의 의미:</h6>
                        <div class="alert alert-success">
                            <strong>${successMeans}</strong>
                        </div>

                        <h6 class="mb-2">통계:</h6>
                        <ul>
                            <li>총 성공 횟수: <strong>${count}회</strong></li>
                            <li>에이전트 ID: <code>${agentId}</code></li>
                        </ul>

                        <div class="alert alert-info mt-3">
                            <small>
                                <strong>💡 참고:</strong><br>
                                성공은 해당 에이전트가 작업을 완료하고 결과를 반환했음을 의미합니다.
                                실제 비즈니스 승인 여부는 Approval Queue에서 확인하세요.
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if any
    const existing = document.getElementById('successDetailModal');
    if (existing) existing.remove();

    document.body.insertAdjacentHTML('beforeend', modal);
    const modalEl = new bootstrap.Modal(document.getElementById('successDetailModal'));
    modalEl.show();
}

function showFailureDetail(agentId, teamName, count) {
    const modal = `
        <div class="modal fade" id="failureDetailModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title">❌ ${teamName} - 실패 상세</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <h6 class="mb-3">실패 원인:</h6>
                        <ul>
                            <li>API 키 오류</li>
                            <li>입력 데이터 형식 오류</li>
                            <li>네트워크 연결 문제</li>
                            <li>에이전트 내부 로직 오류</li>
                        </ul>

                        <h6 class="mb-2">통계:</h6>
                        <ul>
                            <li>총 실패 횟수: <strong>${count}회</strong></li>
                            <li>에이전트 ID: <code>${agentId}</code></li>
                        </ul>

                        <div class="alert alert-warning mt-3">
                            <small>
                                <strong>⚠️ 조치 필요:</strong><br>
                                실패가 반복되면 서버 로그를 확인하거나 관리자에게 문의하세요.
                            </small>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">닫기</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if any
    const existing = document.getElementById('failureDetailModal');
    if (existing) existing.remove();

    document.body.insertAdjacentHTML('beforeend', modal);
    const modalEl = new bootstrap.Modal(document.getElementById('failureDetailModal'));
    modalEl.show();
}

function openExecuteModal(agentId, teamName) {
    currentAgentId = agentId;
    const displayInfo = AGENT_DISPLAY_INFO[agentId];

    document.getElementById('modalAgentName').textContent = teamName;

    const formContainer = document.getElementById('inputFormContainer');
    const schema = AGENT_INPUT_SCHEMAS[agentId] || { fields: [] };

    if (schema.fields.length === 0) {
        // 입력 필드가 없는 경우 - 설명을 하단으로
        formContainer.innerHTML = `
            <form id="executeForm">
                <div class="text-center py-4">
                    <div class="mb-3">
                        <i class="bi bi-check-circle" style="font-size: 3rem; color: #10b981;"></i>
                    </div>
                    <h5 class="mb-3">바로 실행 가능합니다</h5>
                    <p class="text-muted mb-4">
                        ${displayInfo?.description || '에이전트 설명'}
                    </p>
                </div>
                <div class="alert alert-light border" style="font-size: 0.9em;">
                    <strong>💡 참고:</strong> 이 에이전트는 현재 수동 입력이 필요하지 않습니다.
                </div>
            </form>
        `;
    } else {
        let formHtml = `
            <div class="mb-4">
                <div class="d-flex align-items-start">
                    <div class="flex-shrink-0">
                        <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                            <span style="font-size: 1.5rem;">📋</span>
                        </div>
                    </div>
                    <div class="flex-grow-1 ms-3">
                        <h6 class="mb-1">이 에이전트가 하는 일</h6>
                        <p class="text-muted mb-0" style="font-size: 0.9em;">
                            ${displayInfo?.description || '에이전트 설명'}
                        </p>
                    </div>
                </div>
            </div>
            <form id="executeForm">
        `;

        schema.fields.forEach((field, index) => {
            formHtml += `<div class="mb-3">`;
            formHtml += `<label class="form-label fw-bold">${field.label}${field.required ? ' <span class="text-danger">*</span>' : ''}</label>`;

            if (field.type === 'textarea') {
                formHtml += `<textarea class="form-control" name="${field.name}" ${field.required ? 'required' : ''}
                            placeholder="${field.placeholder || ''}" rows="3" style="resize: vertical;"></textarea>`;
            } else if (field.type === 'select') {
                formHtml += `<select class="form-select" name="${field.name}" ${field.required ? 'required' : ''}>`;
                formHtml += `<option value="">선택하세요...</option>`;
                field.options.forEach(opt => {
                    formHtml += `<option value="${opt}">${opt}</option>`;
                });
                formHtml += `</select>`;
            } else if (field.type === 'checkbox') {
                formHtml += `
                    <div class="form-check form-switch">
                        <input type="checkbox" class="form-check-input" name="${field.name}" id="${field.name}" role="switch">
                        <label class="form-check-label" for="${field.name}">활성화</label>
                    </div>
                `;
            } else {
                formHtml += `<input type="${field.type}" class="form-control" name="${field.name}"
                            ${field.required ? 'required' : ''} placeholder="${field.placeholder || ''}">`;
            }

            if (field.placeholder) {
                formHtml += `<small class="form-text text-muted">예: ${field.placeholder}</small>`;
            }

            formHtml += `</div>`;
        });

        formHtml += `
            </form>
            <div class="alert alert-light border mt-3" style="font-size: 0.85em;">
                <strong>💡 필수 입력 항목:</strong> <span class="text-danger">*</span> 표시된 항목은 반드시 입력해야 합니다.
            </div>
        `;
        formContainer.innerHTML = formHtml;
    }

    const modal = new bootstrap.Modal(document.getElementById('executeModal'));
    modal.show();
}

document.getElementById('executeBtn').addEventListener('click', async () => {
    if (!currentAgentId) return;

    const form = document.getElementById('executeForm');
    if (form && !form.checkValidity()) {
        form.reportValidity();
        return;
    }

    const formData = form ? new FormData(form) : new FormData();
    const input = {};

    for (const [key, value] of formData.entries()) {
        if (value === '') continue;

        // Handle array fields (comma-separated)
        if (key === 'key_features' || key === 'source_options') {
            input[key] = value.split(',').map(v => v.trim()).filter(v => v);
        } else if (key === 'source_price_cny' || key === 'price' || key === 'weight_kg' || key === 'source_price') {
            input[key] = parseFloat(value);
        } else if (key === 'compliance_mode') {
            input[key] = true;
        } else {
            input[key] = value;
        }
    }

    // Show loading
    const executeBtn = document.getElementById('executeBtn');
    const originalText = executeBtn.textContent;
    executeBtn.disabled = true;
    executeBtn.textContent = '⏳ 실행 중...';

    try {
        const response = await fetch('/api/agents/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                agent: currentAgentId,
                input: input,
                save_to_queue: false
            })
        });

        const result = await response.json();
        const displayInfo = AGENT_DISPLAY_INFO[currentAgentId];

        // Display result in agent card
        const resultBox = document.getElementById(`result-${currentAgentId}`);
        resultBox.classList.add('show');

        if (result.status === 'completed') {
            resultBox.innerHTML = `
                <div class="alert alert-success mb-2">
                    <strong>✅ 성공: ${displayInfo?.success_means || '작업 완료'}</strong>
                </div>
                <small class="text-muted">실행 시각: ${new Date().toLocaleTimeString()}</small>
                <details class="mt-2">
                    <summary style="cursor: pointer; color: #6c757d; font-size: 0.85em;">📄 상세 결과 보기</summary>
                    <pre class="mt-2" style="font-size: 0.75em;">${JSON.stringify(result.result, null, 2)}</pre>
                </details>
            `;
        } else {
            resultBox.innerHTML = `
                <div class="alert alert-danger mb-2">
                    <strong>❌ 실패</strong><br>
                    <small>${result.error || result.message}</small>
                </div>
                <small class="text-muted">실행 시각: ${new Date().toLocaleTimeString()}</small>
            `;
        }

        // Close modal
        bootstrap.Modal.getInstance(document.getElementById('executeModal')).hide();

        // Refresh status
        setTimeout(() => loadAgentStatus(), 1000);

    } catch (error) {
        console.error('Execution failed:', error);
        alert('⚠️ 실행 실패: ' + error.message);
    } finally {
        executeBtn.disabled = false;
        executeBtn.textContent = originalText;
    }
});

document.getElementById('refreshAll').addEventListener('click', () => {
    loadAgentStatus();
});

function showError(message) {
    const container = document.getElementById('agentContainer');
    container.innerHTML = `
        <div class="col-12">
            <div class="alert alert-danger">${message}</div>
        </div>
    `;
}

// Initial load
loadAgentStatus();

// Auto-refresh every 30 seconds
setInterval(loadAgentStatus, 30000);
