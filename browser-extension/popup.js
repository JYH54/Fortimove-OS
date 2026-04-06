/**
 * FORTIMOVE Sourcing - Popup Script
 */

const WORKBENCH_BASE = 'http://localhost:8051';

let currentData = null;
let currentTab = null;

// ── 초기화 ──────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    // 현재 탭 가져오기
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentTab = tab;

    if (!tab || !tab.url) {
        showNotSupported();
        return;
    }

    const supported = /iherb\.com|amazon\.(com|co\.jp|co\.uk)|taobao\.com|tmall\.com|1688\.com|rakuten\.co\.jp/.test(tab.url);
    if (!supported) {
        showNotSupported();
        return;
    }

    // 타오바오/티몰/1688은 스크롤로 lazy load하므로 메시지 변경
    const isChinaSite = /taobao\.com|tmall\.com|1688\.com/.test(tab.url);
    if (isChinaSite) {
        document.getElementById('loading').innerHTML = '페이지 스크롤 중...<br><span style="font-size:10px;">(lazy load 이미지 수집, 약 5초 소요)</span>';
    }

    // content script에게 데이터 추출 요청
    try {
        const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
        if (response && response.success) {
            currentData = response.data;
            displayProduct(currentData);
        } else {
            showError('상품 정보를 추출할 수 없습니다: ' + (response?.error || '알 수 없는 오류'));
        }
    } catch (e) {
        // content script가 아직 로드되지 않은 경우 재시도
        try {
            await chrome.scripting.executeScript({
                target: { tabId: tab.id },
                files: ['content.js']
            });
            await new Promise(r => setTimeout(r, 500));
            const response = await chrome.tabs.sendMessage(tab.id, { action: 'extract' });
            if (response && response.success) {
                currentData = response.data;
                displayProduct(currentData);
                return;
            }
        } catch (e2) {}
        showError('content script 로드 실패. 페이지를 새로고침하세요.');
    }
});

// ── UI 업데이트 ──────────────────────

function showNotSupported() {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('notSupported').style.display = 'block';
}

function showError(msg) {
    document.getElementById('loading').style.display = 'none';
    const s = document.getElementById('status');
    s.className = 'status show error';
    s.textContent = msg;
}

function displayProduct(data) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('productInfo').style.display = 'block';

    const platformLabels = {
        iherb: '🇺🇸 iHerb',
        amazon: '🇺🇸 Amazon',
        taobao: '🇨🇳 타오바오',
        tmall: '🇨🇳 티몰',
        '1688': '🇨🇳 1688',
        rakuten: '🇯🇵 라쿠텐',
    };
    if (data.country === 'JP' && data.platform === 'iherb') platformLabels.iherb = '🇯🇵 iHerb JP';
    if (data.country === 'JP' && data.platform === 'amazon') platformLabels.amazon = '🇯🇵 Amazon JP';

    document.getElementById('platform').textContent = platformLabels[data.platform] || data.platform;
    document.getElementById('title').textContent = (data.title || '-').substring(0, 100);
    document.getElementById('brand').textContent = data.brand || '-';
    document.getElementById('category').textContent = data.category || '-';
    document.getElementById('price').textContent = data.price || '-';
    document.getElementById('imgCount').textContent = `${(data.images || []).length}개`;

    // 이미지 프리뷰
    const preview = document.getElementById('imagePreview');
    preview.innerHTML = (data.images || []).slice(0, 8).map(url =>
        `<img src="${url}" alt="" onerror="this.style.display='none'">`
    ).join('');

    // 카테고리 자동 매핑
    const catMap = {
        'supplement': 'supplement', 'supplements': 'supplement',
        'vitamin': 'supplement', 'vitamins': 'supplement',
        'wellness': 'wellness', 'health': 'wellness',
        'protein': 'supplement', 'nutrition': 'supplement',
        'beauty': 'beauty', 'skincare': 'beauty',
        'fitness': 'fitness', 'sports': 'fitness',
        'food': 'food', 'grocery': 'food',
    };
    const catLower = (data.category || '').toLowerCase();
    for (const [key, val] of Object.entries(catMap)) {
        if (catLower.includes(key)) {
            document.getElementById('catSelect').value = val;
            break;
        }
    }

    // 가격 자동 입력 (숫자 추출)
    if (data.price) {
        const priceNum = parseFloat(data.price.toString().replace(/[^0-9.]/g, ''));
        if (priceNum > 0) document.getElementById('srcPrice').value = priceNum;
    }
}

// ── 전송 ──────────────────────

document.getElementById('sendBtn').addEventListener('click', async () => {
    if (!currentData) return;

    const btn = document.getElementById('sendBtn');
    const status = document.getElementById('status');

    btn.disabled = true;
    btn.textContent = '전송 중...';
    status.className = 'status show loading';
    status.textContent = '워크벤치로 전송 중...';

    try {
        const category = document.getElementById('catSelect').value;
        const srcPrice = parseFloat(document.getElementById('srcPrice').value) || 0;
        const srcWeight = parseFloat(document.getElementById('srcWeight').value) || 0.5;
        const workflow = document.getElementById('workflow').value;

        const payload = {
            source_url: currentData.url,
            source_title: currentData.title,
            source_brand: currentData.brand,
            source_category: category,
            source_price: srcPrice,
            source_country: currentData.country || 'US',
            weight_kg: srcWeight,
            images: currentData.images || [],
            description: currentData.description || '',
            workflow_name: workflow,
            platform: currentData.platform,
        };

        const res = await fetch(`${WORKBENCH_BASE}/api/bi/extension/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();

        if (data.status === 'success') {
            status.className = 'status show success';
            status.textContent = `✓ 전송 완료! 워크벤치를 여는 중...`;

            // 워크벤치 탭 열기
            const workbenchUrl = data.review_id
                ? `${WORKBENCH_BASE}/workbench?review=${data.review_id}`
                : `${WORKBENCH_BASE}/workbench?ext=${data.token}`;

            setTimeout(() => {
                chrome.tabs.create({ url: workbenchUrl });
                window.close();
            }, 800);
        } else {
            throw new Error(data.error || '전송 실패');
        }
    } catch (e) {
        status.className = 'status show error';
        status.textContent = '전송 실패: ' + e.message;
        btn.disabled = false;
        btn.textContent = '워크벤치로 전송 & 분석 시작';
    }
});

document.getElementById('openWorkbench').addEventListener('click', (e) => {
    e.preventDefault();
    chrome.tabs.create({ url: `${WORKBENCH_BASE}/workbench` });
});
