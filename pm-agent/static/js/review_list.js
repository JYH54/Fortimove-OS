// Review List JavaScript

const API_BASE = '/api/phase4/review';

let allReviews = [];
let filteredReviews = [];
let currentSort = { field: 'score', order: 'desc' }; // Default: 점수 높은 순

// Load reviews on page load
document.addEventListener('DOMContentLoaded', () => {
    loadReviews();

    document.getElementById('statusFilter').addEventListener('change', applyFilters);
    document.getElementById('searchInput').addEventListener('input', applyFilters);
    document.getElementById('refreshBtn').addEventListener('click', loadReviews);

    // Sort button listeners
    document.getElementById('sortScoreBtn')?.addEventListener('click', () => toggleSort('score'));
    document.getElementById('sortDateBtn')?.addEventListener('click', () => toggleSort('date'));
});

async function loadReviews() {
    try {
        const response = await fetch(`${API_BASE}/list/all?limit=100`);
        const data = await response.json();

        allReviews = data.items || [];
        filteredReviews = allReviews;

        updateStats();
        renderReviewList();
    } catch (error) {
        console.error('Failed to load reviews:', error);
        document.getElementById('reviewListBody').innerHTML =
            '<tr><td colspan="9" class="text-center text-danger">Failed to load reviews</td></tr>';
    }
}

function toggleSort(field) {
    if (currentSort.field === field) {
        // Toggle order
        currentSort.order = currentSort.order === 'desc' ? 'asc' : 'desc';
    } else {
        // Change field, default to desc
        currentSort.field = field;
        currentSort.order = 'desc';
    }

    // Update button states
    const scoreBtn = document.getElementById('sortScoreBtn');
    const dateBtn = document.getElementById('sortDateBtn');

    if (field === 'score') {
        scoreBtn.classList.add('active');
        dateBtn.classList.remove('active');
        scoreBtn.textContent = currentSort.order === 'desc' ? '점수 ↓' : '점수 ↑';
    } else {
        dateBtn.classList.add('active');
        scoreBtn.classList.remove('active');
        dateBtn.textContent = currentSort.order === 'desc' ? '날짜 ↓' : '날짜 ↑';
    }

    renderReviewList();
}

function applyFilters() {
    const statusFilter = document.getElementById('statusFilter').value;
    const searchText = document.getElementById('searchInput').value.toLowerCase();

    filteredReviews = allReviews.filter(review => {
        // Status filter
        if (statusFilter && review.review_status !== statusFilter) {
            return false;
        }

        // Search filter
        if (searchText) {
            const title = (review.source_title || '').toLowerCase();
            const reviewId = (review.review_id || '').toLowerCase();
            if (!title.includes(searchText) && !reviewId.includes(searchText)) {
                return false;
            }
        }

        return true;
    });

    renderReviewList();
}

function updateStats() {
    document.getElementById('totalCount').textContent = allReviews.length;

    const pendingCount = allReviews.filter(r =>
        r.review_status === 'draft' || r.review_status === 'under_review'
    ).length;
    document.getElementById('pendingCount').textContent = pendingCount;

    const approvedCount = allReviews.filter(r =>
        r.review_status === 'approved_for_export' || r.review_status === 'approved_for_upload'
    ).length;
    document.getElementById('approvedCount').textContent = approvedCount;
}

function renderReviewList() {
    const tbody = document.getElementById('reviewListBody');

    if (filteredReviews.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-5">검색 결과가 없습니다</td></tr>';
        return;
    }

    // Sort reviews
    const sorted = [...filteredReviews].sort((a, b) => {
        let comparison = 0;
        if (currentSort.field === 'score') {
            comparison = (b.score || 0) - (a.score || 0);
        } else if (currentSort.field === 'date') {
            const dateA = new Date(a.created_at || 0);
            const dateB = new Date(b.created_at || 0);
            comparison = dateB - dateA;
        }
        return currentSort.order === 'desc' ? comparison : -comparison;
    });

    tbody.innerHTML = sorted.map(review => {
        const reviewId = review.review_id || '-';
        const title = review.source_title || '-';
        const score = review.score || 0;
        const decision = review.decision || '-';
        const status = review.review_status || 'draft';
        const updated = formatDate(review.updated_at);

        // Check if has primary image
        const hasPrimaryImage = '❓'; // Unknown without image review data

        // Status badge (한국어)
        const statusLabels = {draft:'초안',under_review:'검토중',approved_for_export:'승인',approved_for_upload:'업로드',hold:'보류',rejected:'거부'};
        const statusBadge = `<span class="badge status-${status}">${statusLabels[status]||status}</span>`;

        // Score badge
        const scoreBadge = score >= 70 ? `<span class="badge bg-success">${score}</span>` :
                          score >= 50 ? `<span class="badge bg-warning text-dark">${score}</span>` :
                          `<span class="badge bg-danger">${score}</span>`;

        return `
            <tr>
                <td><small>${reviewId.substring(0, 8)}...</small></td>
                <td>${title}</td>
                <td>${scoreBadge}</td>
                <td><span class="badge bg-info">${decision}</span></td>
                <td>${statusBadge}</td>
                <td><small>${updated}</small></td>
                <td>
                    <a href="/workbench?review=${reviewId}" class="btn btn-sm btn-primary">열기</a>
                </td>
            </tr>
        `;
    }).join('');
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleString('ko-KR', {
            year: '2-digit',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return dateStr;
    }
}
