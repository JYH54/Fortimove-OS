// Review Detail JavaScript

const API_BASE = '/api/phase4/review';

let currentReviewId = null;
let currentReview = null;
let currentImages = null;

// Get review_id from URL
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;
    const match = path.match(/\/review\/detail\/([^\/]+)/);
    if (match) {
        currentReviewId = match[1];
        document.getElementById('reviewIdDisplay').textContent = `Review: ${currentReviewId.substring(0, 12)}...`;
        loadReviewDetail();
        loadImages();
    } else {
        showError('Invalid review ID');
    }

    // Attach event listeners
    document.getElementById('saveDraftBtn').addEventListener('click', saveDraft);
    document.getElementById('holdBtn').addEventListener('click', () => changeStatus('hold'));
    document.getElementById('rejectBtn').addEventListener('click', () => changeStatus('reject'));
    document.getElementById('approveExportBtn').addEventListener('click', () => changeStatus('approve-export'));
    document.getElementById('exportNaverBtn').addEventListener('click', () => exportCSV('naver'));
    document.getElementById('exportCoupangBtn').addEventListener('click', () => exportCSV('coupang'));
});

async function loadReviewDetail() {
    try {
        const response = await fetch(`${API_BASE}/${currentReviewId}`);
        if (!response.ok) throw new Error('Failed to load review');

        currentReview = await response.json();

        // Display source information
        if (currentReview.source_url) {
            const urlEl = document.getElementById('sourceUrl');
            urlEl.href = currentReview.source_url;
            urlEl.textContent = currentReview.source_url.substring(0, 60) + '...';
        }
        document.getElementById('sourceTitle').textContent = currentReview.source_title || '-';
        document.getElementById('sourceCategory').textContent = currentReview.category || currentReview.product_category || '-';
        document.getElementById('sourcePriceCny').textContent = currentReview.source_price_cny
            ? '¥' + currentReview.source_price_cny
            : '-';
        document.getElementById('sourceWeight').textContent = currentReview.weight_kg
            ? currentReview.weight_kg + 'kg'
            : '-';

        // Display risk flags
        const riskFlags = currentReview.risk_flags || [];
        const riskFlagsEl = document.getElementById('riskFlags');
        if (Array.isArray(riskFlags) && riskFlags.length > 0) {
            riskFlagsEl.innerHTML = riskFlags.map(flag =>
                `<span class="badge bg-warning text-dark">⚠️ ${flag}</span>`
            ).join(' ');
        } else {
            riskFlagsEl.innerHTML = '<span class="badge bg-success">✅ 리스크 없음</span>';
        }

        // Display suggested tags
        const suggestedTags = currentReview.suggested_tags || currentReview.generated_naver_tags || [];
        const tagsArray = Array.isArray(suggestedTags) ? suggestedTags : parseTagsJSON(suggestedTags);
        const suggestedTagsEl = document.getElementById('suggestedTags');
        if (tagsArray.length > 0) {
            suggestedTagsEl.innerHTML = tagsArray.slice(0, 10).map(tag =>
                `<span class="badge bg-light text-dark">#${tag}</span>`
            ).join(' ');
        } else {
            suggestedTagsEl.innerHTML = '<span class="badge bg-secondary">태그 없음</span>';
        }

        // Display generated content (READ-ONLY)
        document.getElementById('genScore').textContent = currentReview.score || 0;
        document.getElementById('genDecision').textContent = currentReview.decision || '-';

        // Naver content
        document.getElementById('genNaverTitle').textContent = currentReview.generated_naver_title || '-';
        document.getElementById('genNaverDesc').textContent = currentReview.generated_naver_description || '-';

        // Coupang content
        document.getElementById('genCoupangTitle').textContent = currentReview.generated_coupang_title || '-';
        document.getElementById('genCoupangDesc').textContent = currentReview.generated_coupang_description || '-';

        // Price
        document.getElementById('genPrice').textContent = currentReview.generated_price
            ? '₩' + currentReview.generated_price.toLocaleString()
            : '-';

        // Display generated tags
        const genNaverTagsDiv = document.getElementById('genNaverTags');
        const genNaverTags = parseTagsJSON(currentReview.generated_naver_tags);
        genNaverTagsDiv.innerHTML = genNaverTags.map(tag =>
            `<span class="badge bg-secondary">${tag}</span>`
        ).join(' ');

        // Pre-fill reviewed content (EDITABLE) with reviewed or fallback to generated
        document.getElementById('revNaverTitle').value = currentReview.reviewed_naver_title || currentReview.generated_naver_title || '';
        document.getElementById('revNaverDesc').value = currentReview.reviewed_naver_description || currentReview.generated_naver_description || '';
        document.getElementById('revCoupangTitle').value = currentReview.reviewed_coupang_title || currentReview.generated_coupang_title || '';
        document.getElementById('revCoupangDesc').value = currentReview.reviewed_coupang_description || currentReview.generated_coupang_description || '';
        document.getElementById('revPrice').value = currentReview.reviewed_price || currentReview.generated_price || '';
        document.getElementById('revNotes').value = currentReview.review_notes || '';

        // Reviewed tags
        const revNaverTags = parseTagsJSON(currentReview.reviewed_naver_tags) || parseTagsJSON(currentReview.generated_naver_tags);
        document.getElementById('revNaverTags').value = revNaverTags.join(', ');

        // Update status display with help text
        const status = currentReview.review_status || 'draft';
        document.getElementById('currentStatus').textContent = status;
        document.getElementById('currentStatus').className = `badge fs-6 status-${status}`;

        // Status-specific help text
        const statusHelp = {
            'draft': '💡 AI 생성 콘텐츠를 검토하고 수정하세요',
            'under_review': '✏️ 이미지를 선택하고 콘텐츠를 편집하세요',
            'hold': '⏸️ 추가 정보가 필요합니다',
            'approved_for_export': '✅ CSV 다운로드 가능',
            'approved_for_upload': '🎉 최종 승인됨, 업로드 대기 중',
            'rejected': '❌ 등록 불가 처리됨'
        };
        document.getElementById('statusHelp').textContent = statusHelp[status] || '';

        // Show/hide export section based on status
        const exportSection = document.getElementById('exportSection');
        if (status === 'approved_for_export' || status === 'approved_for_upload') {
            exportSection.classList.remove('d-none');
        } else {
            exportSection.classList.add('d-none');
        }

    } catch (error) {
        console.error('Failed to load review:', error);
        showError('Failed to load review details');
    }
}

async function loadImages() {
    try {
        const response = await fetch(`${API_BASE}/${currentReviewId}/images`);
        if (!response.ok) throw new Error('Failed to load images');

        currentImages = await response.json();

        renderImages();
    } catch (error) {
        console.error('Failed to load images:', error);
        document.getElementById('imagePanel').innerHTML =
            '<div class="alert alert-warning">No images available</div>';
    }
}

function renderImages() {
    if (!currentImages || !currentImages.reviewed_images) {
        return;
    }

    const imagePanel = document.getElementById('imagePanel');
    const reviewedImages = currentImages.reviewed_images;

    imagePanel.innerHTML = reviewedImages.map((img, idx) => {
        const primaryBadge = img.is_primary ? '<div class="image-primary-badge">⭐ PRIMARY</div>' : '';
        const excludedClass = img.is_excluded ? 'excluded' : '';
        const primaryClass = img.is_primary ? 'primary' : '';
        const excludeBtn = img.is_excluded ? '✅' : '❌';

        return `
            <div class="image-item ${primaryClass} ${excludedClass}" data-image-id="${img.image_id}">
                ${primaryBadge}
                <span class="image-badge" onclick="toggleExclude('${img.image_id}')">${excludeBtn}</span>
                <img src="${img.url}" alt="Product image" onclick="setPrimary('${img.image_id}')">
                <div class="image-order">#${img.display_order + 1}</div>
            </div>
        `;
    }).join('');
}

async function setPrimary(imageId) {
    try {
        const response = await fetch(`${API_BASE}/${currentReviewId}/images/set-primary`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_id: imageId,
                operator: 'console_user'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.errors?.[0] || 'Failed to set primary');
        }

        showSuccess('Primary image updated');
        await loadImages();
    } catch (error) {
        showError(error.message);
    }
}

async function toggleExclude(imageId) {
    const img = currentImages.reviewed_images.find(i => i.image_id === imageId);
    const newExcluded = !img.is_excluded;

    try {
        const response = await fetch(`${API_BASE}/${currentReviewId}/images/exclude`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                image_id: imageId,
                excluded: newExcluded,
                operator: 'console_user'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.errors?.[0] || 'Failed to exclude image');
        }

        showSuccess(newExcluded ? 'Image excluded' : 'Image restored');
        await loadImages();
    } catch (error) {
        showError(error.message);
    }
}

async function saveDraft() {
    try {
        const payload = {
            reviewed_naver_title: document.getElementById('revNaverTitle').value,
            reviewed_naver_description: document.getElementById('revNaverDesc').value,
            reviewed_naver_tags: parseTagsInput(document.getElementById('revNaverTags').value),
            reviewed_coupang_title: document.getElementById('revCoupangTitle').value,
            reviewed_coupang_description: document.getElementById('revCoupangDesc').value,
            reviewed_price: parseFloat(document.getElementById('revPrice').value) || null,
            review_notes: document.getElementById('revNotes').value
        };

        const response = await fetch(`${API_BASE}/${currentReviewId}/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to save draft');

        showSuccess('Draft saved successfully');
        await loadReviewDetail();
    } catch (error) {
        showError('Failed to save draft: ' + error.message);
    }
}

async function changeStatus(action) {
    const endpoints = {
        'hold': 'hold',
        'reject': 'reject',
        'approve-export': 'approve-export'
    };

    const endpoint = endpoints[action];
    if (!endpoint) return;

    try {
        const response = await fetch(`${API_BASE}/${currentReviewId}/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reviewed_by: 'console_user',
                review_notes: document.getElementById('revNotes').value
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail?.message || 'Status change failed');
        }

        showSuccess(`Status changed to ${action}`);
        await loadReviewDetail();
    } catch (error) {
        showError(error.message);
    }
}

async function exportCSV(channel) {
    try {
        const response = await fetch(`${API_BASE}/export/csv`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                review_ids: [currentReviewId],
                channel: channel,
                exported_by: 'console_user'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Export failed');
        }

        const data = await response.json();

        // Download CSV
        const blob = new Blob([data.csv_data], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `${channel}_export_${currentReviewId.substring(0, 8)}.csv`;
        link.click();

        showSuccess(`Exported ${data.row_count} rows to ${channel} CSV`);
    } catch (error) {
        showError('Export failed: ' + error.message);
    }
}

function parseTagsJSON(tagsJson) {
    if (!tagsJson) return [];
    try {
        const parsed = JSON.parse(tagsJson);
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function parseTagsInput(tagsStr) {
    if (!tagsStr) return [];
    return tagsStr.split(',').map(t => t.trim()).filter(t => t);
}

function showSuccess(message) {
    const feedback = document.getElementById('actionFeedback');
    feedback.innerHTML = `<div class="alert alert-success">${message}</div>`;
    setTimeout(() => feedback.innerHTML = '', 3000);
}

function showError(message) {
    const feedback = document.getElementById('actionFeedback');
    feedback.innerHTML = `<div class="alert alert-danger">${message}</div>`;
}
