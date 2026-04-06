/**
 * Fortimove Workbench — 통합 워크플로우 컨트롤러
 * Vertical accordion/timeline layout — all steps on one scrolling page
 */
const WB = {
    // ── 상태 ───────────────────────────────────────
    currentStep: 1,
    maxReachedStep: 1,
    reviewId: null,
    redesignId: null,
    reviewData: null,
    autoSaveTimer: null,

    COUNTRY_INFO: {
        CN: { currency: 'CNY', symbol: '¥', hint: '타오바오, 1688, 알리바바' },
        JP: { currency: 'JPY', symbol: '¥', hint: '라쿠텐, 아마존 재팬' },
        US: { currency: 'USD', symbol: '$', hint: '아마존, 아이허브, eBay' },
        GB: { currency: 'GBP', symbol: '£', hint: '아마존 UK' },
    },

    REVIEW_API: '/api/phase4/review',
    REDESIGN_API: '/api/redesign',

    // Step titles for summary generation
    STEP_TITLES: {
        1: '소싱 분석',
        2: '리스크 검토',
        3: '가격/등록',
        4: '상세페이지 디자인',
        5: '최종 확인',
    },

    // ── 초기화 ─────────────────────────────────────
    init() {
        // URL 자동 국가 감지
        document.getElementById('srcUrl').addEventListener('input', function () {
            const url = this.value.toLowerCase();
            const sel = document.getElementById('srcCountry');
            if (url.includes('taobao') || url.includes('1688') || url.includes('tmall')) sel.value = 'CN';
            else if (url.includes('rakuten') || url.includes('amazon.co.jp')) sel.value = 'JP';
            else if (url.includes('amazon.com') || url.includes('iherb')) sel.value = 'US';
            else if (url.includes('amazon.co.uk')) sel.value = 'GB';
            WB.updateCurrency();
        });

        // 최근 작업 패널 외부 클릭 닫기
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.recent-dropdown')) {
                document.getElementById('recentPanel').classList.remove('open');
            }
        });

        // 시간 업데이트
        setInterval(() => {
            document.getElementById('statusTime').textContent = new Date().toLocaleTimeString('ko-KR');
        }, 1000);

        WB.updateCurrency();
        WB.loadRecent();
        WB.loadScoutProducts();
        WB.refreshThroughput();
        // 30초마다 처리량 자동 갱신
        setInterval(() => WB.refreshThroughput(), 30000);

        // A3: 전역 키보드 단축키 (Q=빠른승인 열기, 오버레이 내부에서 방향키/엔터/ESC)
        document.addEventListener('keydown', (e) => {
            // 입력 필드 포커스 중이면 스킵
            const tag = (e.target.tagName || '').toLowerCase();
            if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

            // Q: 빠른 승인 열기 (오버레이 닫힌 상태에서만)
            if (!WB.qa.open && (e.key === 'q' || e.key === 'Q')) {
                e.preventDefault();
                WB.openQuickApproval();
                return;
            }
            // 오버레이 열린 상태의 단축키
            if (WB.qa.open) {
                if (e.key === 'Escape') { e.preventDefault(); WB.closeQuickApproval(); }
                else if (e.key === 'ArrowRight') { e.preventDefault(); WB.qaAction('approve'); }
                else if (e.key === 'ArrowLeft')  { e.preventDefault(); WB.qaAction('reject'); }
                else if (e.key === 'ArrowUp')    { e.preventDefault(); WB.qaAction('hold'); }
                else if (e.key === 'ArrowDown')  { e.preventDefault(); WB.qaAction('skip'); }
                else if (e.key === 'Enter')      { e.preventDefault(); WB.qaAction('detail'); }
            }
        });

        // URL 파라미터로 리뷰 자동 로드 (/workbench?review=xxx)
        const params = new URLSearchParams(window.location.search);
        const reviewParam = params.get('review');
        if (reviewParam) {
            WB.loadFromUrl(reviewParam);
        }

        // Initialize the accordion — step 1 is open by default
        WB.updateAllCards();
    },

    async loadFromUrl(reviewId) {
        WB.reviewId = reviewId;
        WB.showLoading('리뷰 데이터 로드 중...');
        await WB.loadReviewData();
        WB.hideLoading();

        if (!WB.reviewData) { WB.toast('리뷰를 찾을 수 없습니다'); return; }

        // 모든 단계 데이터 채우기
        WB.populateStep2();
        WB.populateStep3();

        // 확장 프로그램에서 전송한 이미지가 있으면 자동 로드
        const sd = WB.reviewData._sourceData || {};
        const extImages = sd.ext_images || sd.images || [];
        if (extImages.length > 0) {
            WB.loadExtensionImages(extImages);
        }

        // 기존 리디자인이 있는지 확인
        await WB.checkExistingRedesign();

        // 가장 진행된 스텝으로 이동
        const status = WB.reviewData.review_status || 'draft';
        const hasContent = WB.reviewData.content_status === 'completed' || WB.reviewData.generated_naver_title;

        if (WB.redesignId) {
            WB.maxReachedStep = 5;
            WB.activateStep(4); // 리디자인 있으면 에디터로
        } else if (hasContent) {
            WB.maxReachedStep = 3;
            WB.activateStep(3); // 콘텐츠 있으면 편집으로
        } else {
            WB.maxReachedStep = 2;
            WB.activateStep(2); // 기본: 분석
        }
    },

    async loadExtensionImages(imageUrls) {
        // 확장 프로그램에서 전달된 이미지 URL들을 File 객체로 변환하여 detailFiles에 설정
        WB.detailFiles = [];
        WB.classifiedImages = { main: [], option: [], detail: [] };

        try {
            for (let i = 0; i < Math.min(imageUrls.length, 50); i++) {
                const url = imageUrls[i];
                try {
                    const res = await fetch(url);
                    if (!res.ok) continue;
                    const blob = await res.blob();
                    const ext = blob.type.includes('png') ? 'png' : 'jpg';
                    const filename = i === 0 ? `main_01.${ext}` : `detail_${String(i).padStart(2, '0')}.${ext}`;
                    const file = new File([blob], filename, { type: blob.type || 'image/jpeg' });
                    file._index = i;
                    file._category = i === 0 ? 'main' : 'detail';
                    WB.detailFiles.push(file);
                    WB.classifiedImages[file._category].push(file);
                } catch (e) { /* skip failed images */ }
            }

            if (WB.detailFiles.length > 0) {
                WB.renderClassification();
                WB.toast(`확장 프로그램에서 ${WB.detailFiles.length}개 이미지 로드됨`);
            }
        } catch (e) {
            console.warn('확장 이미지 로드 실패:', e);
        }
    },

    async checkExistingRedesign() {
        if (!WB.reviewId) return;
        try {
            const res = await fetch(`${WB.REDESIGN_API}/queue?limit=50`);
            const data = await res.json();
            const items = data.items || [];
            // 이 리뷰에 연결된 리디자인 찾기
            const match = items.find(i => i.review_id === WB.reviewId && i.status === 'completed');
            if (match) {
                WB.redesignId = match.redesign_id;
            }
        } catch (e) { /* ignore */ }
    },

    // ══════════════════════════════════════════════════
    // ACCORDION NAVIGATION SYSTEM
    // ══════════════════════════════════════════════════

    /**
     * Activate a step — expand it, collapse others that are completed,
     * update sidebar, and scroll into view.
     */
    activateStep(n) {
        WB.currentStep = n;
        if (n > WB.maxReachedStep) WB.maxReachedStep = n;

        // Step 4 진입 시 에디터 초기화
        if (n === 4) {
            if (WB.redesignId) {
                // Defer init until the card is expanded and visible
                setTimeout(() => FMEditor.init(WB.redesignId), 100);
            } else {
                WB.toast('Step 3 상세페이지 탭에서 이미지를 업로드하고 리디자인을 시작하세요');
                WB.activateStep(3);
                WB.switchTab('detail');
                return;
            }
        }

        // Step 5 진입 시 완료 정보 채우기
        if (n === 5) {
            WB.populateStep5();
        }

        // Step 3 자동저장 시작/중지
        if (n === 3) WB.startAutoSave();
        else WB.stopAutoSave();

        WB.updateAllCards();
        WB.updateSidebar();
        WB.updateStatusBar();

        // Scroll the active step into view
        WB.scrollToStep(n);
    },

    /**
     * Toggle a step card open/closed (clicking the header).
     * Only completed or active steps can be toggled.
     */
    toggleStep(n) {
        const card = document.getElementById('stepCard' + n);
        if (!card) return;

        // If this step is pending and beyond maxReachedStep, don't allow opening
        if (n > WB.maxReachedStep) return;

        // If this is the current active step, just toggle its content visibility
        if (n === WB.currentStep) {
            card.classList.toggle('collapsed');
            return;
        }

        // If clicking a completed or reachable step, make it the active step
        WB.activateStep(n);
    },

    /**
     * Scroll to a specific step card smoothly.
     */
    scrollToStep(n) {
        const card = document.getElementById('stepCard' + n);
        if (!card) return;
        setTimeout(() => {
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 50);
    },

    /**
     * Update the visual state of all step cards.
     * - Active step: expanded with blue border
     * - Completed steps (before active): collapsed with green border + summary
     * - Future steps (after maxReached): collapsed, greyed out
     */
    updateAllCards() {
        for (let i = 1; i <= 5; i++) {
            const card = document.getElementById('stepCard' + i);
            const badge = document.getElementById('shBadge' + i);
            if (!card || !badge) continue;

            card.classList.remove('active', 'completed', 'pending', 'collapsed');

            if (i === WB.currentStep) {
                card.classList.add('active');
                badge.className = 'sh-badge badge-active';
                badge.textContent = '진행중';
            } else if (i < WB.currentStep || i <= WB.maxReachedStep) {
                card.classList.add('completed', 'collapsed');
                badge.className = 'sh-badge badge-completed';
                badge.textContent = '완료';
                WB.updateStepSummary(i);
            } else {
                card.classList.add('pending', 'collapsed');
                badge.className = 'sh-badge badge-pending';
                badge.textContent = '대기';
            }
        }
    },

    /**
     * Update the summary line shown when a step is collapsed.
     */
    updateStepSummary(n) {
        const el = document.getElementById('shSummary' + n);
        if (!el) return;
        const d = WB.reviewData;

        switch (n) {
            case 1:
                el.textContent = d ? (d.source_title || '').substring(0, 40) + ' — 분석 완료' : '분석 완료';
                break;
            case 2:
                if (d) {
                    const score = d.score || 0;
                    const decision = d.decision || '';
                    el.textContent = `점수 ${score} · ${decision || '검토 완료'}`;
                } else {
                    el.textContent = '검토 완료';
                }
                break;
            case 3:
                if (d) {
                    const title = d.reviewed_naver_title || d.generated_naver_title || '';
                    el.textContent = title ? title.substring(0, 35) + '...' : '콘텐츠 편집 완료';
                } else {
                    el.textContent = '편집 완료';
                }
                break;
            case 4:
                el.textContent = WB.redesignId ? '리디자인 완료' : '디자인 완료';
                break;
            case 5:
                el.textContent = '등록 준비 완료';
                break;
        }
    },

    /**
     * Update the fixed left sidebar progress indicators.
     */
    updateSidebar() {
        document.querySelectorAll('.ps-step').forEach(el => {
            const step = parseInt(el.dataset.step);
            el.classList.remove('active', 'completed', 'pending');

            if (step === WB.currentStep) {
                el.classList.add('active');
            } else if (step < WB.currentStep || step <= WB.maxReachedStep) {
                el.classList.add('completed');
            } else {
                el.classList.add('pending');
            }
        });

        // Update status text in sidebar
        for (let i = 1; i <= 5; i++) {
            const statEl = document.getElementById('psStat' + i);
            if (!statEl) continue;
            if (i === WB.currentStep) statEl.textContent = '진행중';
            else if (i < WB.currentStep || i <= WB.maxReachedStep) statEl.textContent = '완료';
            else statEl.textContent = '대기';
        }
    },

    // Backward-compatible alias: old code calls goToStep
    goToStep(n) {
        WB.activateStep(n);
    },

    updateStepper() {
        // Legacy — now handled by updateSidebar + updateAllCards
        WB.updateSidebar();
        WB.updateAllCards();
    },

    updateStatusBar() {
        if (WB.reviewData) {
            document.getElementById('statusProduct').textContent = (WB.reviewData.source_title || '-').substring(0, 30);
            document.getElementById('statusReviewId').textContent = WB.reviewId ? 'ID: ' + WB.reviewId.substring(0, 8) : '-';
            document.getElementById('statusScore').textContent = WB.reviewData.score ? '점수: ' + WB.reviewData.score : '-';
        }
    },

    // ═══════════════════════════════════════════════
    // Daily Scout 트렌드 상품
    // ═══════════════════════════════════════════════
    _scoutFilterDebounceTimer: null,
    _scoutFilterDebounce() {
        clearTimeout(WB._scoutFilterDebounceTimer);
        WB._scoutFilterDebounceTimer = setTimeout(() => WB.loadScoutProducts(), 350);
    },

    async loadScoutProducts() {
        const el = document.getElementById('scoutList');
        if (!el) return;
        // A5 필터 값 수집
        const minScore = parseInt(document.getElementById('scoutMinScore')?.value || '0') || 0;
        const exclBl = document.getElementById('scoutBlacklist')?.checked !== false;
        const params = new URLSearchParams({
            limit: '10',
            min_score: String(minScore),
            exclude_blacklist: exclBl ? 'true' : 'false',
        });
        try {
            const res = await fetch(`/api/bi/scout/products?${params}`);
            const d = await res.json();
            const items = d.data || d.products || [];

            // A5: 컷 카운트 표시
            const cutEl = document.getElementById('scoutCutInfo');
            if (cutEl) {
                if (d.cut_count > 0) {
                    const reasons = d.cut_reasons || {};
                    const topReasons = Object.entries(reasons)
                        .sort((a,b) => b[1]-a[1]).slice(0,3)
                        .map(([k,v]) => `${k} ${v}`).join(' · ');
                    cutEl.textContent = `🚫 ${d.cut_count}건 사전 컷 (${topReasons})`;
                } else {
                    cutEl.textContent = '';
                }
            }

            if (!Array.isArray(items) || items.length === 0) {
                el.innerHTML = '<div style="color:var(--text-muted);padding:10px;">필터 조건에 맞는 상품이 없습니다 (점수/블랙리스트 조정)</div>';
                return;
            }

            el.innerHTML = items.map((p, i) => {
                const name = p.product_name || p.title || '';
                const score = p.trend_score || 0;
                const demand = p.korea_demand || '';
                const region = p.region || '';
                const risk = p.risk_status || '';
                const price = p.price || '';
                const url = p.url || '';
                const regionFlag = {japan:'🇯🇵',us:'🇺🇸',china:'🇨🇳',uk:'🇬🇧'}[region] || '🌍';
                const demandColor = demand === '높음' ? 'var(--green)' : demand === '보통' ? 'var(--yellow)' : 'var(--text-muted)';
                const riskBadge = risk === '통과' ? 'st-ok' : risk === '보류' ? 'st-warn' : 'st-err';

                return `<div onclick="WB.selectScoutProduct(${i})" style="display:flex;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--border);border-radius:8px;margin-bottom:6px;cursor:pointer;transition:all .15s;background:var(--card);"
                    onmouseover="this.style.borderColor='var(--blue)'" onmouseout="this.style.borderColor='var(--border)'">
                    <div style="font-size:1.2rem;">${regionFlag}</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name}</div>
                        <div style="font-size:11px;color:var(--text-muted);">${price} · ${p.brand || ''}</div>
                    </div>
                    <div style="text-align:right;min-width:60px;">
                        <div style="font-size:14px;font-weight:800;color:${score>=80?'var(--green)':score>=60?'var(--yellow)':'var(--text-muted)'};">${score}</div>
                        <div style="font-size:10px;color:${demandColor};">${demand}</div>
                    </div>
                </div>`;
            }).join('');

            // 데이터 저장
            WB._scoutProducts = items;
        } catch (e) {
            el.innerHTML = '<div style="color:var(--text-muted);padding:10px;">Scout 서비스 연결 실패</div>';
        }
    },

    selectScoutProduct(index) {
        const p = WB._scoutProducts?.[index];
        if (!p) return;

        // URL 자동 입력
        document.getElementById('srcUrl').value = p.url || '';

        // 상품명
        document.getElementById('srcTitle').value = p.product_name || '';

        // 국가 자동 매핑
        const regionMap = { japan: 'JP', us: 'US', china: 'CN', uk: 'GB' };
        const country = regionMap[p.region] || 'US';
        document.getElementById('srcCountry').value = country;
        WB.updateCurrency();

        // 카테고리 자동 매핑
        const catMap = {
            '영양제/보충제': 'supplement', '면역력': 'supplement', '비타민': 'supplement',
            '뷰티': 'beauty', '스킨케어': 'beauty',
            '운동용품': 'fitness', '스포츠': 'fitness',
            '건강식품': 'food', '식품': 'food',
        };
        document.getElementById('srcCategory').value = catMap[p.category] || 'supplement';

        WB.toast(`${(p.product_name || '').substring(0, 20)} 선택됨 — 분석 시작을 누르세요`);

        // 스크롤 올리기
        document.getElementById('srcUrl').scrollIntoView({ behavior: 'smooth', block: 'center' });
    },

    _scoutProducts: [],

    // ═══════════════════════════════════════════════
    // STEP 1: 소싱
    // ═══════════════════════════════════════════════
    updateCurrency() {
        const country = document.getElementById('srcCountry').value;
        const info = WB.COUNTRY_INFO[country] || WB.COUNTRY_INFO.US;
        document.getElementById('currencyLabel').textContent = info.currency;
    },

    // ═══════════════════════════════════════════════
    // A2: 단일/벌크 소싱 모드
    // ═══════════════════════════════════════════════
    setSourcingMode(mode) {
        const single = document.getElementById('srcModeSingle');
        const bulk = document.getElementById('srcModeBulk');
        const btnS = document.getElementById('modeSingle');
        const btnB = document.getElementById('modeBulk');
        if (mode === 'bulk') {
            single.style.display = 'none';
            bulk.style.display = 'flex';
            btnS.classList.remove('active');
            btnB.classList.add('active');
            // 텍스트영역 change 이벤트로 카운터 갱신
            const ta = document.getElementById('srcUrlBulk');
            if (!ta.dataset.bound) {
                ta.addEventListener('input', () => {
                    const urls = WB._parseBulkUrls(ta.value);
                    document.getElementById('bulkCount').textContent = `${urls.length}개 URL 감지 (최대 10)`;
                });
                ta.dataset.bound = '1';
            }
        } else {
            single.style.display = 'flex';
            bulk.style.display = 'none';
            btnS.classList.add('active');
            btnB.classList.remove('active');
        }
    },

    _parseBulkUrls(text) {
        return text.split(/\r?\n/)
            .map(s => s.trim())
            .filter(s => s.length > 0 && /^https?:\/\//i.test(s))
            .slice(0, 10);
    },

    async runBulkSourcing() {
        const urls = WB._parseBulkUrls(document.getElementById('srcUrlBulk').value);
        if (urls.length === 0) { WB.toast('유효한 URL이 없습니다'); return; }

        const btn = document.getElementById('srcBulkBtn');
        btn.disabled = true; btn.textContent = `분석 중... (0/${urls.length})`;

        // 진행 리스트 초기화
        const listEl = document.getElementById('bulkProgressList');
        listEl.style.display = 'block';
        listEl.innerHTML = urls.map((u, i) => `
            <div class="bulk-item" id="bulk-item-${i}">
                <div class="bi-idx">#${i+1}</div>
                <div class="bi-url" title="${u}">${u}</div>
                <div class="bi-status waiting">대기</div>
            </div>
        `).join('');

        // 공통 파라미터
        const commonInput = {
            source_country: document.getElementById('srcCountry').value,
            weight_kg: parseFloat(document.getElementById('srcWeight').value) || 0.5,
            market: 'korea',
            category: document.getElementById('srcCategory').value,
        };
        const workflow = document.getElementById('srcWorkflow').value;

        // 3개씩 동시 처리
        const CONCURRENCY = 3;
        let doneCount = 0, successCount = 0, failCount = 0;

        const runOne = async (idx, url) => {
            const itemEl = document.getElementById(`bulk-item-${idx}`);
            const statusEl = itemEl.querySelector('.bi-status');
            statusEl.className = 'bi-status running';
            statusEl.textContent = '분석 중';
            try {
                const res = await fetch('/api/workflows/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        workflow_name: workflow,
                        user_input: { ...commonInput, source_url: url },
                        save_to_queue: true,
                    }),
                });
                const data = await res.json();
                if (data.status === 'completed') {
                    successCount++;
                    const rid = data.result?.review_id || data.review_id
                        || data.result?.queue_item?.review_id || '';
                    statusEl.className = 'bi-status done';
                    statusEl.innerHTML = rid
                        ? `<a href="/workbench?review=${rid}" style="color:#3fb950;text-decoration:none;">✓ 완료 →</a>`
                        : '✓ 완료';
                } else {
                    failCount++;
                    statusEl.className = 'bi-status fail';
                    statusEl.textContent = '✗ ' + (data.error || '실패').substring(0, 30);
                }
            } catch (e) {
                failCount++;
                statusEl.className = 'bi-status fail';
                statusEl.textContent = '✗ 오류';
            } finally {
                doneCount++;
                btn.textContent = `분석 중... (${doneCount}/${urls.length})`;
            }
        };

        // Concurrency pool
        const queue = urls.map((u, i) => ({ i, u }));
        const workers = Array.from({ length: Math.min(CONCURRENCY, urls.length) }, async () => {
            while (queue.length > 0) {
                const item = queue.shift();
                if (!item) break;
                await runOne(item.i, item.u);
            }
        });
        await Promise.all(workers);

        btn.disabled = false;
        btn.textContent = '일괄 분석 시작';
        WB.toast(`완료: 성공 ${successCount}건 / 실패 ${failCount}건`);

        // 처리량 카운터·최근 작업 갱신
        WB.refreshThroughput();
        WB.loadRecent();
    },

    async runSourcing() {
        const url = document.getElementById('srcUrl').value.trim();
        if (!url) { WB.toast('URL을 입력하세요'); return; }

        const btn = document.getElementById('srcBtn');
        btn.disabled = true; btn.textContent = '분석 중...';

        // 프로그레스 표시
        const progress = document.getElementById('analysisProgress');
        progress.classList.add('active');
        WB.animateProgress();

        try {
            const res = await fetch('/api/workflows/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    workflow_name: document.getElementById('srcWorkflow').value,
                    user_input: {
                        source_url: url,
                        source_title: document.getElementById('srcTitle').value,
                        source_price: parseFloat(document.getElementById('srcPrice').value) || 0,
                        source_price_cny: document.getElementById('srcCountry').value === 'CN'
                            ? parseFloat(document.getElementById('srcPrice').value) || 0 : null,
                        source_country: document.getElementById('srcCountry').value,
                        weight_kg: parseFloat(document.getElementById('srcWeight').value) || 0.5,
                        market: 'korea',
                        category: document.getElementById('srcCategory').value,
                    },
                    save_to_queue: true,
                })
            });

            const data = await res.json();

            if (data.status === 'completed') {
                // review_id 추출 (여러 위치에서 탐색)
                WB.reviewId = data.result?.review_id || data.review_id || null;

                if (!WB.reviewId && data.result?.queue_item) {
                    WB.reviewId = data.result.queue_item.review_id;
                }

                // 폴백: review_id 없으면 최신 리뷰 목록에서 찾기
                if (!WB.reviewId) {
                    try {
                        const listRes = await fetch(`${WB.REVIEW_API}/list/all?limit=1`);
                        const listData = await listRes.json();
                        const items = listData.items || listData.reviews || [];
                        if (Array.isArray(items) && items.length > 0) {
                            WB.reviewId = items[0].review_id;
                        }
                    } catch (e) { /* ignore */ }
                }

                if (WB.reviewId) {
                    // 워크플로우 결과에서 직접 데이터 보강
                    await WB.loadReviewData();
                    WB.enrichFromWorkflowResult(data.result);
                    WB.populateStep2();
                    progress.classList.remove('active');
                    WB.activateStep(2);
                } else {
                    WB.toast('분석 완료 — 리뷰 목록에서 확인하세요');
                    progress.classList.remove('active');
                }
            } else {
                WB.toast('분석 실패: ' + (data.error || data.message || '알 수 없는 오류'));
                progress.classList.remove('active');
            }
        } catch (e) {
            WB.toast('오류: ' + e.message);
            progress.classList.remove('active');
        }

        btn.disabled = false; btn.textContent = '분석 시작';
    },

    animateProgress() {
        const fill = document.getElementById('progressFill');
        const text = document.getElementById('progressText');
        const steps = [
            { pct: 15, label: 'URL 크롤링 중...' },
            { pct: 35, label: '리스크 분석 중...' },
            { pct: 55, label: '마진 계산 중...' },
            { pct: 75, label: 'SEO 최적화 중...' },
            { pct: 90, label: '콘텐츠 생성 중...' },
        ];
        let i = 0;
        const iv = setInterval(() => {
            if (i >= steps.length) { clearInterval(iv); fill.style.width = '100%'; return; }
            fill.style.width = steps[i].pct + '%';
            text.textContent = steps[i].label;
            i++;
        }, 2000);
    },

    // ═══════════════════════════════════════════════
    // STEP 2: 분석
    // ═══════════════════════════════════════════════
    async loadReviewData() {
        if (!WB.reviewId) return;
        try {
            const res = await fetch(`${WB.REVIEW_API}/${WB.reviewId}`);
            WB.reviewData = await res.json();

            // source_data_json 파싱
            let sd = WB.reviewData.source_data_json;
            if (typeof sd === 'string') { try { sd = JSON.parse(sd); } catch { sd = {}; } }
            WB.reviewData._sourceData = sd || {};

            // raw_agent_output 파싱 (마진 에이전트 결과)
            let rao = WB.reviewData.raw_agent_output;
            if (typeof rao === 'string') { try { rao = JSON.parse(rao); } catch { rao = {}; } }
            WB.reviewData._rawOutput = rao || {};

            // source_data 내 all_results에서 소싱/마진 결과 추출
            const allResults = (sd || {}).all_results || {};
            WB.reviewData._sourcingResult = allResults.sourcing || {};
            WB.reviewData._marginResult = allResults.margin || rao || {};

            // JSON 필드들 파싱
            ['product_summary_json', 'risk_assessment_json', 'sales_strategy_json', 'detail_content_json', 'image_design_json'].forEach(key => {
                let val = WB.reviewData[key];
                if (typeof val === 'string') { try { val = JSON.parse(val); } catch { val = null; } }
                WB.reviewData['_' + key.replace('_json', '')] = val || {};
            });
        } catch (e) {
            WB.toast('리뷰 데이터 로드 실패');
        }
    },

    // 워크플로우 결과에서 DB에 아직 반영 안 된 데이터 보강
    enrichFromWorkflowResult(result) {
        if (!result || !WB.reviewData) return;
        const d = WB.reviewData;

        // sourcing 결과
        const sourcing = result.sourcing?.output || result.sourcing || {};
        if (!d._risk_assessment || !d._risk_assessment.risk_level) {
            d._risk_assessment = {
                risk_level: sourcing.risk_flags?.length > 0 ? 'MEDIUM' : 'LOW',
                ip_notes: sourcing.legal_analysis?.ip_risk_summary || sourcing.risk_details?.ip_risk || '',
                claim_notes: sourcing.risk_details?.expression_risk || '',
                final_decision: sourcing.sourcing_decision || d.decision || '',
            };
        }
        if (!d.decision) d.decision = sourcing.sourcing_decision || '';

        // margin 결과
        const margin = result.margin?.output || result.margin || {};
        if (!d.generated_price && margin.final_selling_price_krw) {
            d.generated_price = margin.final_selling_price_krw;
        }
        if (margin.margin_rate) {
            d._marginRate = margin.margin_rate;
        }

        // scoring 결과
        const scoring = result.scoring || {};
        if (scoring.score) {
            d.score = scoring.score;
            d.decision = scoring.decision || d.decision;
        }

        // auto_approval
        const approval = result.auto_approval || {};
        if (!d.score && approval.evaluation?.score) {
            d.score = approval.evaluation.score;
        }
    },

    populateStep2() {
        const d = WB.reviewData;
        if (!d) return;
        const sd = d._sourceData || {};
        const risk = d._risk_assessment || {};
        const summary = d._product_summary || {};
        const marginData = d._marginResult || {};
        const rawOut = d._rawOutput || {};

        // 점수
        const score = d.score || 0;
        document.getElementById('s2Score').textContent = score;
        document.getElementById('s2ScoreBar').style.width = score + '%';
        const scoreColor = score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--yellow)' : 'var(--red)';
        document.getElementById('s2Score').style.color = scoreColor;
        document.getElementById('s2ScoreBar').style.background = scoreColor;
        document.getElementById('s2Decision').textContent = d.decision || (score >= 70 ? '승인 추천' : '수동 검토');

        // 리스크 (risk_assessment_json에서 추출)
        const riskLevel = risk.risk_level || 'LOW';
        const risksEl = document.getElementById('s2Risks');
        const riskClass = riskLevel === 'HIGH' ? 'risk-high' : riskLevel === 'MEDIUM' ? 'risk-medium' : 'risk-low';
        let riskHtml = `<span class="risk-badge ${riskClass}">리스크: ${riskLevel}</span>`;
        if (risk.ip_notes) riskHtml += ` <span class="risk-badge risk-medium" style="font-size:11px;">${risk.ip_notes.substring(0, 60)}</span>`;
        risksEl.innerHTML = riskHtml;

        // 태그
        const tags = WB.parseTags(d.generated_naver_tags);
        if (tags.length > 0) {
            document.getElementById('s2Tags').innerHTML = tags.slice(0, 8).map(t =>
                `<span style="background:rgba(88,166,255,.1);color:var(--blue);padding:2px 8px;border-radius:4px;font-size:11px;">#${t}</span>`
            ).join('');
        } else {
            document.getElementById('s2Tags').innerHTML = '<span style="color:var(--text-muted);font-size:11px;">태그 없음</span>';
        }

        // 마진 (all_results.margin → _marginResult → _rawOutput 순서)
        const costBreakdown = marginData.cost_breakdown || rawOut.cost_breakdown || {};
        const marginAnalysis = marginData.margin_analysis || rawOut.margin_analysis || {};
        const inputData = (sd.input || sd || {});

        // 크롤링된 가격 (sourceData.all_results.sourcing.extracted_info.price_text)
        const allResults = sd.all_results || {};
        const sourcingExtracted = (allResults.sourcing || {}).extracted_info || {};
        const crawledPriceText = sourcingExtracted.price_text || '';

        // 소싱가: 크롤링 가격 → cost_breakdown → 수동 입력 순서
        const cur = costBreakdown.source_currency || 'USD';
        const curSymbols = { CNY: '¥', JPY: '¥', USD: '$', KRW: '₩', GBP: '£' };
        const curSym = curSymbols[cur] || cur + ' ';
        const srcForeign = costBreakdown.source_price_foreign || inputData.source_price || 0;
        const srcKrw = costBreakdown.source_price_krw || 0;
        const totalCost = costBreakdown.total_cost_krw || 0;
        const targetPrice = marginAnalysis.target_price || rawOut.target_price;
        const sellPrice = d.generated_price || targetPrice;

        // 소싱가 표시: 크롤링가 → 외화 → 원화 → 총비용
        if (crawledPriceText) {
            document.getElementById('s2SrcPrice').textContent = crawledPriceText;
        } else if (srcForeign > 0) {
            document.getElementById('s2SrcPrice').textContent = curSym + Number(srcForeign).toLocaleString();
        } else if (srcKrw > 0) {
            document.getElementById('s2SrcPrice').textContent = '₩' + Number(srcKrw).toLocaleString();
        } else if (totalCost > 0) {
            document.getElementById('s2SrcPrice').textContent = '₩' + Number(totalCost).toLocaleString() + ' (총비용)';
        } else {
            document.getElementById('s2SrcPrice').textContent = '가격 미수집';
        }
        document.getElementById('s2SellPrice').textContent = sellPrice ? '₩' + Number(sellPrice).toLocaleString() : '-';

        const netMargin = marginAnalysis.net_margin_rate || d._marginRate;
        if (netMargin) {
            document.getElementById('s2Margin').textContent = Math.round(netMargin) + '%';
        } else if (sellPrice && totalCost) {
            const m = Math.round((1 - totalCost / sellPrice) * 100);
            document.getElementById('s2Margin').textContent = m > 0 ? m + '%' : '-';
        }

        // 비용 상세 표시 (마진 카드 하단)
        const costDetailEl = document.getElementById('s2CostDetail');
        if (costDetailEl && totalCost > 0) {
            const ship = costBreakdown.shipping_fee_krw || 0;
            const pkg = costBreakdown.packaging_fee_krw || 0;
            const reg = costBreakdown.regulation_cost_krw || 0;
            const parts = [];
            if (srcKrw > 0) parts.push(`상품원가 ₩${Number(srcKrw).toLocaleString()}`);
            if (ship > 0) parts.push(`배송 ₩${Number(ship).toLocaleString()}`);
            if (pkg > 0) parts.push(`포장 ₩${Number(pkg).toLocaleString()}`);
            if (reg > 0) parts.push(`인증/규제 ₩${Number(reg).toLocaleString()}`);
            parts.push(`총비용 ₩${Number(totalCost).toLocaleString()}`);
            costDetailEl.innerHTML = parts.join(' · ');
            costDetailEl.style.display = 'block';
        } else if (costDetailEl) {
            costDetailEl.style.display = 'none';
        }

        // 마진 판정
        const finalDecision = rawOut.final_decision || marginData.final_decision || '';
        if (finalDecision) {
            document.getElementById('s2Decision').textContent += ' | ' + finalDecision;
        }

        // 플랫폼 프리뷰 — 빈 카드 숨기기
        const naverCard = document.getElementById('s2NaverCard');
        const coupangCard = document.getElementById('s2CoupangCard');
        if (d.generated_naver_title) {
            document.getElementById('s2NaverTitle').textContent = d.generated_naver_title;
            if (naverCard) naverCard.style.display = '';
        } else {
            if (naverCard) naverCard.style.display = 'none';
        }
        if (d.generated_coupang_title) {
            document.getElementById('s2CoupangTitle').textContent = d.generated_coupang_title;
            if (coupangCard) coupangCard.style.display = '';
        } else {
            if (coupangCard) coupangCard.style.display = 'none';
        }

        // 핵심 요약 — 빈 칸 숨기기
        const summaryText = summary.positioning_summary || summary.summary || d.generated_naver_description || '';
        const summaryCard = document.getElementById('s2SummaryCard');
        if (summaryText && summaryText !== '-') {
            document.getElementById('s2Summary').textContent = summaryText.substring(0, 300);
            if (summaryCard) summaryCard.style.display = '';
        } else {
            if (summaryCard) summaryCard.style.display = 'none';
        }

        // 콘텐츠 미생성 안내
        const notice = document.getElementById('s2ContentNotice');
        if (!d.generated_naver_title && d.content_status !== 'completed') {
            notice.style.display = 'block';
        } else {
            notice.style.display = 'none';
        }

        WB.updateStatusBar();
        // B3: 이미지 품질 체크 (비동기, 완료되면 배지 표시)
        WB.runImageQualityCheck();
    },

    // ═══════════════════════════════════════════════
    // B3: 썸네일 품질 체커
    // ═══════════════════════════════════════════════
    async runImageQualityCheck() {
        if (!WB.reviewId) return;
        const badgeEl = document.getElementById('s2ImageQualityBadge');
        if (!badgeEl) return;
        badgeEl.innerHTML = '<span style="color:var(--text-muted);font-size:11px;">⏳ 이미지 품질 검사 중...</span>';

        try {
            // 리뷰의 이미지 목록 가져오기
            const imgRes = await fetch(`${WB.REVIEW_API}/${WB.reviewId}/images`);
            if (!imgRes.ok) { badgeEl.innerHTML = ''; return; }
            const imgData = await imgRes.json();
            const originals = imgData.original_images || imgData.originals || [];
            const mainUrl = originals[0]?.image_url || originals[0]?.url;
            const allUrls = originals.map(i => i.image_url || i.url).filter(Boolean).slice(0, 10);

            if (allUrls.length === 0) {
                badgeEl.innerHTML = '<span style="color:var(--text-muted);font-size:11px;">이미지 없음</span>';
                return;
            }

            const batchRes = await fetch('/api/images/quality-check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ urls: allUrls, require_white_bg: false }),
            });
            const batch = await batchRes.json();
            let mainResult = null;
            if (mainUrl) {
                const mRes = await fetch('/api/images/quality-check', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: mainUrl, require_white_bg: true }),
                });
                mainResult = await mRes.json();
            }

            const avg = batch.avg_score || 0;
            const passed = batch.passed || 0;
            const total = batch.total || 0;
            const color = avg >= 80 ? '#3fb950' : avg >= 60 ? '#f39c12' : '#ff6b6b';
            let html = `
                <div style="background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:10px 14px;margin-top:10px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                        <div>
                            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;font-weight:700;">이미지 품질 (B3)</div>
                            <div style="font-size:12px;color:var(--text);margin-top:2px;">
                                평균 <strong style="color:${color};font-size:1.1rem;">${avg}점</strong>
                                · 통과 <strong>${passed}/${total}</strong>
                                ${mainResult ? ` · 대표이미지 <strong style="color:${mainResult.score >= 70 ? '#3fb950' : '#ff6b6b'};">${mainResult.score}점</strong>` : ''}
                            </div>
                        </div>
                        <button onclick="WB.showImageQualityDetail()" style="background:var(--card);border:1px solid var(--border);color:var(--text);padding:5px 12px;border-radius:6px;cursor:pointer;font-size:11px;">상세 보기</button>
                    </div>
                    ${mainResult && mainResult.warnings && mainResult.warnings.length > 0 ? `
                        <div style="margin-top:6px;font-size:10px;color:#f39c12;">
                            ⚠ 대표이미지: ${mainResult.warnings.slice(0,2).join(' · ')}
                        </div>
                    ` : ''}
                </div>
            `;
            badgeEl.innerHTML = html;
            WB._imageQualityDetail = { batch, mainResult };
        } catch (e) {
            badgeEl.innerHTML = '<span style="color:var(--text-muted);font-size:11px;">품질 검사 실패</span>';
        }
    },

    showImageQualityDetail() {
        const d = WB._imageQualityDetail;
        if (!d) return;
        const lines = [];
        if (d.mainResult) {
            lines.push(`📌 대표이미지: ${d.mainResult.score}점`);
            (d.mainResult.warnings || []).forEach(w => lines.push('  · ' + w));
            const m = d.mainResult.meta || {};
            if (m.width) lines.push(`  · ${m.width}x${m.height} ${m.format} ${m.file_size_mb}MB`);
            lines.push('');
        }
        lines.push(`🖼 전체 이미지 (${d.batch.total}장)`);
        (d.batch.results || []).forEach((r, i) => {
            lines.push(`  ${i+1}. ${r.score}점 ${r.pass ? '✓' : '✗'}${r.warnings && r.warnings.length ? ' — ' + r.warnings[0] : ''}`);
        });
        alert(lines.join('\n'));
    },

    async reviewAction(action) {
        if (!WB.reviewId) return;

        try {
            if (action === 'approve') {
                // 1) 승인 처리
                await fetch(`${WB.REVIEW_API}/${WB.reviewId}/approve-export`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'workbench_user' })
                });

                // 2) 콘텐츠 미생성이면 자동 생성 후 Step 3 이동
                const d = WB.reviewData || {};
                const hasContent = d.generated_naver_title || d.generated_coupang_title;
                if (!hasContent) {
                    WB.activateStep(3);
                    WB.toast('콘텐츠 자동 생성 시작...');
                    const tone = document.getElementById('contentTone')?.value || 'premium';
                    const btn = document.getElementById('generateContentBtn');
                    const statusEl = document.getElementById('contentGenStatus');
                    if (btn) { btn.disabled = true; btn.textContent = '생성 중...'; }
                    if (statusEl) {
                        statusEl.style.display = 'block';
                        statusEl.style.background = 'rgba(88,166,255,.1)';
                        statusEl.style.color = 'var(--blue)';
                        statusEl.textContent = `승인 완료 → "${tone}" 톤으로 콘텐츠 자동 생성 중... (30초~1분)`;
                    }
                    try {
                        const res = await fetch(`/api/phase1/review/${WB.reviewId}/generate-all`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ regenerate: true, tone: tone })
                        });
                        const data = await res.json();
                        if (data.status === 'success') {
                            await WB.loadReviewData();
                            WB.populateStep3();
                            if (statusEl) {
                                statusEl.style.background = 'rgba(63,185,80,.1)';
                                statusEl.style.color = 'var(--green)';
                                statusEl.textContent = '✅ 콘텐츠 자동 생성 완료! 각 탭에서 확인·수정하세요.';
                            }
                            WB.toast('승인 + 콘텐츠 생성 완료');
                        } else {
                            if (statusEl) {
                                statusEl.style.background = 'rgba(233,69,96,.1)';
                                statusEl.style.color = 'var(--brand)';
                                statusEl.textContent = '⚠ 자동 생성 실패 — "콘텐츠 생성" 버튼을 직접 눌러주세요.';
                            }
                        }
                    } catch (e) {
                        if (statusEl) {
                            statusEl.style.background = 'rgba(233,69,96,.1)';
                            statusEl.style.color = 'var(--brand)';
                            statusEl.textContent = '⚠ 자동 생성 오류 — "콘텐츠 생성" 버튼을 직접 눌러주세요.';
                        }
                    }
                    if (btn) { btn.disabled = false; btn.textContent = '콘텐츠 생성'; }
                } else {
                    // 이미 콘텐츠 있으면 바로 Step 3
                    WB.populateStep3();
                    WB.activateStep(3);
                }
            } else if (action === 'hold') {
                await fetch(`${WB.REVIEW_API}/${WB.reviewId}/hold`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'workbench_user' })
                });
                WB.toast('보류 처리됨');
            } else if (action === 'reject') {
                await fetch(`${WB.REVIEW_API}/${WB.reviewId}/reject`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'workbench_user' })
                });
                WB.toast('거부 처리됨');
            }
        } catch (e) {
            WB.toast('오류: ' + e.message);
        }
    },

    // ═══════════════════════════════════════════════
    // STEP 3: 편집
    // ═══════════════════════════════════════════════

    async generateContent() {
        if (!WB.reviewId) { WB.toast('리뷰 데이터가 없습니다'); return; }

        const tone = document.getElementById('contentTone').value;
        const btn = document.getElementById('generateContentBtn');
        const statusEl = document.getElementById('contentGenStatus');

        btn.disabled = true;
        btn.textContent = '생성 중...';
        statusEl.style.display = 'block';
        statusEl.style.background = 'rgba(88,166,255,.1)';
        statusEl.style.color = 'var(--blue)';
        statusEl.textContent = `"${tone}" 톤으로 콘텐츠 생성 중... (30초~1분 소요)`;

        try {
            const res = await fetch(`/api/phase1/review/${WB.reviewId}/generate-all`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regenerate: true, tone: tone })
            });
            const data = await res.json();

            if (data.status === 'success') {
                statusEl.style.background = 'rgba(63,185,80,.1)';
                statusEl.style.color = 'var(--green)';
                statusEl.textContent = '콘텐츠 생성 완료! 각 탭에서 확인하세요.';

                // 생성된 데이터로 탭 업데이트
                await WB.loadReviewData();
                WB.populateStep3();

                WB.toast('콘텐츠 생성 완료');
            } else {
                throw new Error(data.detail || data.message || '생성 실패');
            }
        } catch (e) {
            statusEl.style.background = 'rgba(218,54,51,.1)';
            statusEl.style.color = 'var(--red)';
            statusEl.textContent = '생성 실패: ' + e.message;
            WB.toast('콘텐츠 생성 실패: ' + e.message);
        }

        btn.disabled = false;
        btn.textContent = '콘텐츠 생성';
    },

    populateStep3() {
        const d = WB.reviewData;
        if (!d) return;
        const sd = d._sourceData || {};
        const strategy = d._sales_strategy || {};
        const summary = d._product_summary || {};
        const detail = d._detail_content || {};
        const marginData = d._marginResult || {};
        const allResults = sd.all_results || {};
        const sourcingExtracted = (allResults.sourcing || {}).extracted_info || {};
        const costBreakdown = marginData.cost_breakdown || {};
        const marginAnalysis = marginData.margin_analysis || {};

        // 기본정보 탭
        document.getElementById('e3Title').value = d.reviewed_naver_title || d.generated_naver_title || d.source_title || '';
        document.getElementById('e3Category').value = sd.category || (sd.input || {}).category || d.generated_category || '';
        const targetPrice = marginAnalysis.target_price || d.reviewed_price || d.generated_price || '';
        document.getElementById('e3Price').value = targetPrice ? Math.round(Number(targetPrice)) : '';
        const crawledPrice = sourcingExtracted.price_text || '';
        const srcForeign = costBreakdown.source_price_foreign || (sd.input || {}).source_price || '';
        const srcCurrency = costBreakdown.source_currency || '';
        const srcDisplay = crawledPrice || (srcForeign ? `${srcCurrency} ${srcForeign}` : '');
        document.getElementById('e3SrcPrice').value = srcDisplay;
        document.getElementById('e3Notes').value = d.review_notes || '';

        // 네이버 탭
        document.getElementById('e3NaverTitle').value = d.reviewed_naver_title || d.generated_naver_title || detail.naver_title || '';
        document.getElementById('e3NaverDesc').value = d.reviewed_naver_description || d.generated_naver_description || detail.naver_body || '';
        const tags = WB.parseTags(d.reviewed_naver_tags || d.generated_naver_tags) || detail.search_tags || [];
        document.getElementById('e3NaverTags').value = Array.isArray(tags) ? tags.join(', ') : '';

        // 쿠팡 탭
        document.getElementById('e3CoupangTitle').value = d.reviewed_coupang_title || d.generated_coupang_title || detail.coupang_title || '';
        document.getElementById('e3CoupangDesc').value = d.reviewed_coupang_description || d.generated_coupang_description || detail.coupang_body || '';

        // 판매전략 탭
        document.getElementById('e3Positioning').value = summary.positioning_summary || '';
        const uspPoints = summary.usp_points || detail.key_benefits;
        document.getElementById('e3USP').value = Array.isArray(uspPoints) ? uspPoints.join('\n') : (uspPoints || '');
        document.getElementById('e3Target').value = strategy.target_audience || summary.target_customer || '';

        // 콘텐츠 생성 완료 표시
        if (d.content_status === 'completed') {
            const statusEl = document.getElementById('contentGenStatus');
            statusEl.style.display = 'block';
            statusEl.style.background = 'rgba(63,185,80,.1)';
            statusEl.style.color = 'var(--green)';
            statusEl.textContent = '콘텐츠 생성 완료 — 각 탭에서 수정 가능합니다';
        }
    },

    switchTab(tabName) {
        document.querySelectorAll('.edit-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.querySelector(`.edit-tab[data-tab="${tabName}"]`).classList.add('active');
        document.getElementById('tab-' + tabName).classList.add('active');
    },

    async saveDraft() {
        if (!WB.reviewId) return;
        try {
            const payload = {
                reviewed_naver_title: document.getElementById('e3NaverTitle').value,
                reviewed_naver_description: document.getElementById('e3NaverDesc').value,
                reviewed_naver_tags: WB.parseTagsInput(document.getElementById('e3NaverTags').value),
                reviewed_coupang_title: document.getElementById('e3CoupangTitle').value,
                reviewed_coupang_description: document.getElementById('e3CoupangDesc').value,
                reviewed_price: parseFloat(document.getElementById('e3Price').value) || null,
                review_notes: document.getElementById('e3Notes').value,
            };
            await fetch(`${WB.REVIEW_API}/${WB.reviewId}/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            document.getElementById('autosaveStatus').textContent = '저장됨 ' + new Date().toLocaleTimeString('ko-KR');
        } catch (e) {
            document.getElementById('autosaveStatus').textContent = '저장 실패';
        }
    },

    startAutoSave() {
        WB.stopAutoSave();
        WB.autoSaveTimer = setInterval(() => WB.saveDraft(), 30000);
    },
    stopAutoSave() {
        if (WB.autoSaveTimer) { clearInterval(WB.autoSaveTimer); WB.autoSaveTimer = null; }
    },

    // ═══════════════════════════════════════════════
    // 이미지 업로드 + 자동 분류
    // ═══════════════════════════════════════════════
    detailFiles: [],
    classifiedImages: { main: [], option: [], detail: [] },

    handleDetailFiles(files) {
        WB.detailFiles = Array.from(files);
        WB.classifiedImages = { main: [], option: [], detail: [] };

        // 파일명 기반 자동 분류
        WB.detailFiles.forEach((f, i) => {
            const name = f.name.toLowerCase();
            const cat = WB.classifyImage(name, i);
            f._category = cat;
            f._index = i;
            WB.classifiedImages[cat].push(f);
        });

        WB.renderClassification();
    },

    classifyImage(filename, index) {
        const name = filename.toLowerCase();

        // 대표이미지 패턴
        if (/^(main|대표|thumb|primary|cover|hero|title|메인|섬네일)/.test(name)) return 'main';
        if (/_(main|대표|thumb|primary|cover)[\._]/.test(name)) return 'main';

        // 옵션이미지 패턴
        if (/^(option|opt|옵션|color|colour|variant|sku|사이즈|컬러|색상)/.test(name)) return 'option';
        if (/_(option|opt|옵션|color|variant|sku)[\._]/.test(name)) return 'option';
        if (/(red|blue|black|white|pink|green|빨강|파랑|검정|흰색|소형|중형|대형|s_|m_|l_|xl_)/i.test(name)) return 'option';

        // 상세페이지 패턴 (기본)
        if (/^(detail|상세|desc|info|page|content|설명|spec|스펙)/.test(name)) return 'detail';
        if (/_(detail|상세|desc|info|page)[\._]/.test(name)) return 'detail';

        // 숫자만 있는 파일 (01.jpg, 1.png 등) → 첫 번째는 대표, 나머지는 상세
        if (index === 0 && WB.classifiedImages.main.length === 0) return 'main';

        return 'detail'; // 기본값: 상세페이지
    },

    renderClassification() {
        document.getElementById('imageClassification').style.display = 'block';

        const renderGroup = (files, containerId, countId) => {
            document.getElementById(countId).textContent = files.length + '개';
            const container = document.getElementById(containerId);
            container.innerHTML = files.length ? files.map(f => {
                const url = URL.createObjectURL(f);
                const catColors = { main: 'var(--green)', option: 'var(--blue)', detail: 'var(--yellow)' };
                return `<div onclick="WB.cycleCategory(${f._index})" style="width:60px;height:60px;border-radius:6px;overflow:hidden;cursor:pointer;border:2px solid ${catColors[f._category]};position:relative;" title="${f.name}\n클릭하여 분류 변경">
                    <img src="${url}" style="width:100%;height:100%;object-fit:cover;">
                    <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.7);font-size:8px;text-align:center;color:#fff;padding:1px;">${f.name.substring(0, 10)}</div>
                </div>`;
            }).join('') : '<div style="color:var(--text-muted);font-size:11px;">없음</div>';
        };

        renderGroup(WB.classifiedImages.main, 'mainImages', 'mainCount');
        renderGroup(WB.classifiedImages.option, 'optionImages', 'optionCount');
        renderGroup(WB.classifiedImages.detail, 'detailImages', 'detailCount');
    },

    cycleCategory(fileIndex) {
        const f = WB.detailFiles[fileIndex];
        if (!f) return;
        const order = ['main', 'option', 'detail'];
        const curIdx = order.indexOf(f._category);
        const newCat = order[(curIdx + 1) % 3];

        // 기존 분류에서 제거
        WB.classifiedImages[f._category] = WB.classifiedImages[f._category].filter(x => x._index !== fileIndex);
        // 새 분류에 추가
        f._category = newCat;
        WB.classifiedImages[newCat].push(f);

        WB.renderClassification();
        const catLabels = { main: '대표이미지', option: '옵션이미지', detail: '상세페이지' };
        WB.toast(`${f.name.substring(0, 15)} → ${catLabels[newCat]}`);
    },

    async startRedesign() {
        if (!WB.reviewId && WB.detailFiles.length === 0) {
            WB.toast('이미지를 업로드하거나 리뷰 데이터가 필요합니다');
            return;
        }

        // 먼저 편집 내용 저장
        if (WB.reviewId) await WB.saveDraft();

        WB.showLoading('리디자인 준비 중...');

        try {
            const moodtone = document.getElementById('e3Moodtone').value;
            let createData;

            if (WB.detailFiles.length > 0) {
                // 수동 업로드 방식
                const form = new FormData();
                form.append('source_title', document.getElementById('e3Title')?.value || WB.reviewData?.source_title || 'Untitled');
                form.append('moodtone', moodtone);
                form.append('category', document.getElementById('e3Category')?.value || 'general');
                form.append('source_type', 'manual_upload');
                WB.detailFiles.forEach(f => form.append('files', f));

                const createRes = await fetch(`${WB.REDESIGN_API}/upload`, { method: 'POST', body: form });
                createData = await createRes.json();
                if (!createRes.ok) throw new Error(createData.detail || '업로드 실패');
            } else {
                // 리뷰 기반 방식
                const form = new FormData();
                form.append('moodtone', moodtone);

                const createRes = await fetch(`${WB.REDESIGN_API}/from-review/${WB.reviewId}`, {
                    method: 'POST', body: form
                });
                createData = await createRes.json();
                if (!createRes.ok) throw new Error(createData.detail || '리디자인 생성 실패');
            }

            WB.redesignId = createData.redesign_id;

            // 파이프라인 시작
            await fetch(`${WB.REDESIGN_API}/${WB.redesignId}/start`, { method: 'POST' });

            // 폴링
            WB.showLoading('상세페이지 이미지 생성 중...');
            await WB.pollRedesign();

            WB.hideLoading();
            WB.activateStep(4);
        } catch (e) {
            WB.hideLoading();
            WB.toast('리디자인 오류: ' + e.message);
        }
    },

    async pollRedesign() {
        const maxAttempts = 60; // 최대 3분
        for (let i = 0; i < maxAttempts; i++) {
            const res = await fetch(`${WB.REDESIGN_API}/${WB.redesignId}`);
            const data = await res.json();

            if (data.status === 'completed') return;
            if (data.status === 'failed') throw new Error('리디자인 파이프라인 실패');

            await new Promise(r => setTimeout(r, 3000));
        }
        throw new Error('리디자인 타임아웃');
    },

    // ═══════════════════════════════════════════════
    // STEP 5: 완료
    // ═══════════════════════════════════════════════
    populateStep5() {
        const d = WB.reviewData;
        if (d) {
            document.getElementById('s5ProductName').textContent = d.source_title || d.generated_naver_title || '-';
            document.getElementById('s5Score').textContent = d.score || '-';
        }
    },

    downloadZip() {
        if (WB.redesignId) {
            window.open(`${WB.REDESIGN_API}/${WB.redesignId}/download`, '_blank');
        } else {
            WB.toast('다운로드할 리디자인이 없습니다');
        }
    },

    async generateMaterial(type) {
        if (!WB.reviewId) { WB.toast('상품 데이터가 없습니다'); return; }

        const d = WB.reviewData;
        const title = d.generated_naver_title || d.source_title || '';
        const desc = d.generated_naver_description || '';
        const summary = d._product_summary || {};
        const strategy = d._sales_strategy || {};
        const detail = d._detail_content || {};

        const typeConfig = {
            sns: {
                label: 'SNS 콘텐츠 (인스타/블로그)',
                prompt: `이 상품의 인스타그램/네이버 블로그용 SNS 콘텐츠를 한국어로 작성하세요.

상품명: ${title}
핵심 혜택: ${(summary.usp_points || []).join(', ')}
타겟: ${strategy.target_audience || summary.target_customer || ''}

작성 규칙:
- 인스타그램 캡션 (이모지 포함, 200자 이내) 1개
- 네이버 블로그 서론 (3~4줄) 1개
- 해시태그 10개
- 의료 효능 표현 금지`
            },
            blog: {
                label: '블로그 원고',
                prompt: `이 상품의 네이버 블로그 리뷰 원고를 한국어로 작성하세요.

상품명: ${title}
설명: ${desc.substring(0, 200)}
핵심 혜택: ${(summary.usp_points || []).join(', ')}
FAQ: ${(detail.faq || []).map(f => f.q).join(', ')}

작성 규칙:
- 구매 동기 → 개봉기 → 사용 후기 → 총평 구조
- 500~800자
- 자연스러운 체험 리뷰 톤
- 의료 효능 표현 금지, "~에 도움이 될 수 있다" 완곡 표현`
            },
            ad: {
                label: '광고 카피',
                prompt: `이 상품의 네이버 쇼핑 광고 카피를 한국어로 작성하세요.

상품명: ${title}
핵심 혜택: ${(summary.usp_points || []).join(', ')}
타겟: ${strategy.target_audience || ''}

작성:
- 검색 광고 제목 (25자 이내) 3개
- 검색 광고 설명 (45자 이내) 3개
- 배너 광고 문구 (15자 이내) 3개
- 의료 효능 표현 금지`
            },
            review: {
                label: '리뷰 요청 템플릿',
                prompt: `이 상품을 구매한 고객에게 리뷰를 요청하는 메시지를 한국어로 작성하세요.

상품명: ${title}

작성:
- 리뷰 요청 메시지 (네이버 스마트스토어 톡톡용, 100자 이내) 1개
- 포토 리뷰 유도 메시지 (50자 이내) 1개
- 리뷰 작성 포인트 안내 (어떤 점을 써달라는 가이드) 3개
- 정중하고 친근한 톤`
            }
        };

        const config = typeConfig[type];
        if (!config) return;

        document.getElementById('materialTitle').textContent = config.label + ' 생성 중...';
        document.getElementById('materialText').textContent = '';
        document.getElementById('materialResult').style.display = 'block';

        try {
            const res = await fetch('/api/phase1/review/' + WB.reviewId + '/generate-all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ regenerate: false }) // 기존 콘텐츠 유지
            });

            // LLM으로 소재 생성
            const matRes = await fetch('/api/bi/generate-material', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: config.prompt, type: type })
            });
            const matData = await matRes.json();

            document.getElementById('materialTitle').textContent = config.label;
            document.getElementById('materialText').textContent = matData.content || matData.error || '생성 실패';
        } catch (e) {
            document.getElementById('materialTitle').textContent = config.label + ' (오류)';
            document.getElementById('materialText').textContent = '생성 실패: ' + e.message;
        }
    },

    async exportCSV(channel) {
        if (!WB.reviewId) return;
        try {
            const res = await fetch(`${WB.REVIEW_API}/export/csv`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    review_ids: [WB.reviewId],
                    channel: channel,
                    exported_by: 'workbench_user'
                })
            });
            const data = await res.json();
            if (data.csv_data) {
                const blob = new Blob([data.csv_data], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(blob);
                link.download = `${channel}_export.csv`;
                link.click();
                WB.toast('CSV 다운로드 완료');
            }
        } catch (e) {
            WB.toast('CSV 내보내기 실패');
        }
    },

    reset() {
        WB.currentStep = 1;
        WB.maxReachedStep = 1;
        WB.reviewId = null;
        WB.redesignId = null;
        WB.reviewData = null;
        WB.detailFiles = [];
        WB.stopAutoSave();
        if (typeof FMEditor !== 'undefined') FMEditor.destroy();

        // 입력 필드 초기화
        document.getElementById('srcUrl').value = '';
        document.getElementById('srcPrice').value = '';
        document.getElementById('srcTitle').value = '';
        document.getElementById('srcWeight').value = '0.5';
        document.getElementById('analysisProgress').classList.remove('active');
        document.getElementById('progressFill').style.width = '0';

        // 상태바 초기화
        document.getElementById('statusProduct').textContent = '-';
        document.getElementById('statusReviewId').textContent = '-';
        document.getElementById('statusScore').textContent = '-';

        // Clear summaries
        for (let i = 1; i <= 5; i++) {
            const s = document.getElementById('shSummary' + i);
            if (s) s.textContent = '';
        }

        WB.updateAllCards();
        WB.updateSidebar();
        WB.scrollToStep(1);
    },

    // ═══════════════════════════════════════════════
    // A3: 빠른 승인 모드 (키보드 스와이프)
    // ═══════════════════════════════════════════════
    qa: { items: [], idx: 0, open: false, busy: false },

    async openQuickApproval() {
        const overlay = document.getElementById('quickApprovalOverlay');
        overlay.classList.add('active');
        WB.qa.open = true;
        WB.qa.idx = 0;
        document.getElementById('qaStack').innerHTML = '<div class="qa-empty">로딩 중...</div>';
        try {
            const res = await fetch(`${WB.REVIEW_API}/list/all?review_status=draft&limit=50`);
            const d = await res.json();
            const items = (d.items || []).filter(i => {
                const rs = i.review_status || 'draft';
                return rs === 'draft' || rs === 'under_review' || rs === 'hold';
            });
            WB.qa.items = items;
            if (items.length === 0) {
                document.getElementById('qaStack').innerHTML =
                    '<div class="qa-empty">🎉 승인 대기 중인 리뷰가 없습니다</div>';
                document.getElementById('qaProgress').textContent = '0 / 0';
                document.getElementById('qaFooter').innerHTML =
                    '<button class="qa-action skip" onclick="WB.closeQuickApproval()">닫기</button>';
                return;
            }
            WB._renderQaCard();
        } catch (e) {
            document.getElementById('qaStack').innerHTML =
                '<div class="qa-empty">로드 실패: ' + e.message + '</div>';
        }
    },

    closeQuickApproval() {
        document.getElementById('quickApprovalOverlay').classList.remove('active');
        WB.qa.open = false;
        WB.refreshThroughput();
        WB.loadRecent();
    },

    async _renderQaCard() {
        const stack = document.getElementById('qaStack');
        const footer = document.getElementById('qaFooter');
        const prog = document.getElementById('qaProgress');
        const { items, idx } = WB.qa;
        if (idx >= items.length) {
            stack.innerHTML = '<div class="qa-empty">🎉 모든 리뷰 처리 완료!<br><br>처리량 카운터가 갱신되었습니다.</div>';
            footer.innerHTML = '<button class="qa-action skip" onclick="WB.closeQuickApproval()">닫기</button>';
            prog.textContent = `${items.length} / ${items.length} 완료`;
            return;
        }
        const item = items[idx];
        prog.textContent = `${idx + 1} / ${items.length}`;

        let detail = item;
        try {
            const res = await fetch(`${WB.REVIEW_API}/${item.review_id}`);
            if (res.ok) detail = await res.json();
        } catch (e) {}

        const score = detail.score || item.score || 0;
        const scoreClass = score >= 70 ? 'high' : score >= 40 ? 'mid' : 'low';
        const title = detail.source_title || item.source_title || detail.generated_naver_title || '제목 없음';
        const naverTitle = detail.reviewed_naver_title || detail.generated_naver_title || '';
        const coupangTitle = detail.reviewed_coupang_title || detail.generated_coupang_title || '';
        const price = detail.reviewed_price || detail.generated_price || 0;
        const decision = detail.decision || item.decision || '';

        let risksHtml = '<span class="qa-risk green">리스크 없음</span>';
        try {
            const risks = JSON.parse(detail.risk_notes_json || '[]');
            if (Array.isArray(risks) && risks.length > 0) {
                risksHtml = risks.slice(0, 5).map(r => {
                    const level = (r.severity || r.level || 'low').toLowerCase();
                    const cls = level.includes('high') || level.includes('red') ? 'red'
                              : level.includes('med') || level.includes('yellow') ? 'yellow' : 'green';
                    return `<span class="qa-risk ${cls}">${r.label || r.title || r.type || '리스크'}</span>`;
                }).join('');
            }
        } catch (e) {}

        let summaryHtml = '';
        try {
            const ps = JSON.parse(detail.product_summary_json || '{}');
            if (ps.key_features || ps.summary) {
                const feats = Array.isArray(ps.key_features) ? ps.key_features.slice(0, 3).join(' · ') : '';
                summaryHtml = `<div style="font-size:12px;color:var(--text);line-height:1.6;">${ps.summary || feats}</div>`;
            }
        } catch (e) {}

        stack.innerHTML = `
            <div class="qa-card" id="qaCurrent">
                <div class="qa-card-top">
                    <div class="qa-score-big ${scoreClass}">${score}</div>
                    <div class="qa-card-meta">
                        <div class="qa-card-title">${title}</div>
                        <div class="qa-card-sub">${item.review_id?.substring(0,10) || ''} · ${decision || '대기'}</div>
                        ${price > 0 ? `<div class="qa-card-price">₩${Number(price).toLocaleString('ko-KR')}</div>` : ''}
                    </div>
                </div>
                ${summaryHtml ? `<div class="qa-card-section"><div class="qa-card-section-title">핵심 요약</div>${summaryHtml}</div>` : ''}
                <div class="qa-card-section">
                    <div class="qa-card-section-title">리스크</div>
                    <div class="qa-risk-list">${risksHtml}</div>
                </div>
                ${naverTitle ? `<div class="qa-card-section"><div class="qa-card-section-title">네이버 제목</div><div style="font-size:12px;color:var(--text);">${naverTitle}</div></div>` : ''}
                ${coupangTitle ? `<div class="qa-card-section"><div class="qa-card-section-title">쿠팡 제목</div><div style="font-size:12px;color:var(--text);">${coupangTitle}</div></div>` : ''}
            </div>
        `;
        footer.innerHTML = `
            <button class="qa-action reject"  onclick="WB.qaAction('reject')">← 거부</button>
            <button class="qa-action hold"    onclick="WB.qaAction('hold')">↑ 보류</button>
            <button class="qa-action skip"    onclick="WB.qaAction('skip')">↓ 건너뛰기</button>
            <button class="qa-action detail"  onclick="WB.qaAction('detail')">Enter 상세</button>
            <button class="qa-action approve" onclick="WB.qaAction('approve')">→ 승인</button>
        `;
    },

    async qaAction(action) {
        if (WB.qa.busy) return;
        const item = WB.qa.items[WB.qa.idx];
        if (!item) return;
        const card = document.getElementById('qaCurrent');

        // 리스크 레드 플래그 안전장치
        if (action === 'approve') {
            try {
                const risks = JSON.parse(item.risk_notes_json || '[]');
                const red = risks.find(r => (r.severity || '').toLowerCase().includes('high'));
                if (red && !confirm(`⚠ 고위험 리스크 감지:\n${red.label || red.title || ''}\n\n정말 승인하시겠습니까?`)) return;
            } catch (e) {}
        }

        if (action === 'detail') {
            window.location.href = `/workbench?review=${item.review_id}`;
            return;
        }

        WB.qa.busy = true;
        if (card) {
            if (action === 'approve') card.classList.add('swipe-right');
            else if (action === 'reject') card.classList.add('swipe-left');
            else if (action === 'hold') card.classList.add('swipe-up');
            else card.classList.add('swipe-down');
        }

        try {
            if (action === 'approve') {
                await fetch(`${WB.REVIEW_API}/${item.review_id}/approve-export`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'quick_approval' }),
                });
            } else if (action === 'reject') {
                await fetch(`${WB.REVIEW_API}/${item.review_id}/reject`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'quick_approval' }),
                });
            } else if (action === 'hold') {
                await fetch(`${WB.REVIEW_API}/${item.review_id}/hold`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ reviewed_by: 'quick_approval' }),
                });
            }
        } catch (e) {
            WB.toast('오류: ' + e.message);
        }

        setTimeout(() => {
            WB.qa.idx++;
            WB.qa.busy = false;
            WB._renderQaCard();
        }, 280);
    },

    // ═══════════════════════════════════════════════
    // A4: 오늘 처리량 카운터
    // ═══════════════════════════════════════════════
    async refreshThroughput() {
        try {
            const res = await fetch('/api/workbench/throughput');
            const d = await res.json();
            const t = d.today || {}, dl = d.delta || {}, wk = d.week || {};

            const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
            const setDelta = (id, v) => {
                const el = document.getElementById(id); if (!el) return;
                if (v > 0) { el.textContent = `▲ ${v}`; el.className = 'tb-delta up'; }
                else if (v < 0) { el.textContent = `▼ ${Math.abs(v)}`; el.className = 'tb-delta down'; }
                else { el.textContent = '—'; el.className = 'tb-delta flat'; }
            };

            setVal('twStarted', t.started ?? 0);
            setVal('twDecided', t.decided ?? 0);
            setVal('twPending', t.pending ?? 0);
            setDelta('twStartedDelta', dl.started ?? 0);
            setDelta('twDecidedDelta', dl.decided ?? 0);
            const wa = document.getElementById('twWeekAvg');
            if (wa) wa.textContent = `평균 ${wk.avg_per_day ?? 0}`;

            // 7일 스파크라인
            const sparkEl = document.getElementById('twSpark');
            if (sparkEl && Array.isArray(wk.sparkline)) {
                const max = Math.max(1, ...wk.sparkline.map(s => s.count));
                const todayStr = new Date().toISOString().substring(0, 10);
                sparkEl.innerHTML = wk.sparkline.map(s => {
                    const h = Math.max(2, Math.round((s.count / max) * 22));
                    const isToday = s.date === todayStr;
                    return `<div class="bar ${isToday ? 'today' : ''}" style="height:${h}px;" title="${s.date}: ${s.count}건"></div>`;
                }).join('');
            }

            // A1: 스텝별 병목 표시
            const stagesEl = document.getElementById('twStages');
            if (stagesEl && d.stages) {
                const fmt = (sec) => {
                    if (!sec || sec === 0) return '—';
                    if (sec < 60) return `${sec}s`;
                    if (sec < 3600) return `${Math.round(sec/60)}m`;
                    if (sec < 86400) return `${(sec/3600).toFixed(1)}h`;
                    return `${(sec/86400).toFixed(1)}d`;
                };
                const labels = { analysis: '분석', edit: '편집', decide: '결정' };
                const bk = d.bottleneck;
                stagesEl.innerHTML = ['analysis','edit','decide'].map(k => {
                    const s = d.stages[k] || {};
                    const isB = k === bk && s.n > 0;
                    const v = s.n > 0 ? `${fmt(s.median)} (n=${s.n})` : '데이터 부족';
                    return `<span class="stage ${isB?'bottleneck':''}" title="평균 ${fmt(s.avg)} · 중앙값 ${fmt(s.median)} · 샘플 ${s.n}건">${labels[k]} ${v}</span>`;
                }).join('');
            }
        } catch (e) {
            // 조용히 실패 (UI 깨지지 않도록)
        }
    },

    toggleThroughputDetail() {
        // 수동 새로고침
        WB.refreshThroughput();
    },

    // ═══════════════════════════════════════════════
    // 최근 작업
    // ═══════════════════════════════════════════════
    async loadRecent() {
        try {
            const res = await fetch(`${WB.REVIEW_API}/list/all?limit=20`);
            const data = await res.json();
            const items = data.reviews || data.items || data || [];

            if (!Array.isArray(items) || items.length === 0) {
                document.getElementById('recentList').innerHTML =
                    '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px;">작업 내역이 없습니다</div>';
                return;
            }

            document.getElementById('recentList').innerHTML = items.slice(0, 15).map(item => {
                const score = item.score || 0;
                const status = item.review_status || 'draft';
                const statusLabels = {
                    draft: '초안', under_review: '검수중', approved_for_export: '승인',
                    hold: '보류', rejected: '거부', approved_for_upload: '업로드'
                };
                const title = (item.source_title || item.generated_naver_title || '제목 없음').substring(0, 25);
                return `
                    <div class="recent-item" onclick="WB.loadFromRecent('${item.review_id}', '${status}')">
                        <div class="ri-score" style="color:${score >= 70 ? 'var(--green)' : score >= 40 ? 'var(--yellow)' : 'var(--text-muted)'};">${score}</div>
                        <div style="flex:1;min-width:0;">
                            <div class="ri-title">${title}</div>
                            <div class="ri-meta">${item.review_id?.substring(0, 8) || ''}</div>
                        </div>
                        <span class="ri-status st-${status}">${statusLabels[status] || status}</span>
                    </div>
                `;
            }).join('');
        } catch (e) {
            document.getElementById('recentList').innerHTML =
                '<div style="padding:20px;text-align:center;color:var(--text-muted);font-size:13px;">로드 실패</div>';
        }
    },

    async loadFromRecent(reviewId, status) {
        document.getElementById('recentPanel').classList.remove('open');
        await WB.loadFromUrl(reviewId);
    },

    // ═══════════════════════════════════════════════
    // 유틸리티
    // ═══════════════════════════════════════════════
    parseTags(raw) {
        if (!raw) return [];
        if (Array.isArray(raw)) return raw;
        try { const p = JSON.parse(raw); return Array.isArray(p) ? p : []; }
        catch { return []; }
    },

    parseTagsInput(str) {
        if (!str) return [];
        return str.split(',').map(t => t.trim()).filter(t => t);
    },

    showLoading(text) {
        document.getElementById('wbLoadingText').textContent = text || '처리 중...';
        document.getElementById('wbLoading').classList.add('show');
    },
    hideLoading() {
        document.getElementById('wbLoading').classList.remove('show');
    },

    toast(msg) {
        const el = document.getElementById('wbToast');
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(() => el.classList.remove('show'), 3000);
    },
};

function toggleRecent() {
    const panel = document.getElementById('recentPanel');
    panel.classList.toggle('open');
    if (panel.classList.contains('open')) WB.loadRecent();
}

// 초기화
document.addEventListener('DOMContentLoaded', () => WB.init());
