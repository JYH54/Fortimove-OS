/**
 * Phase 1 Review Detail - 상품 기획 워크벤치
 * 콘텐츠 생성 중심 UI
 */

let currentReviewId = null;
let currentData = null;

// ==========================================
// 1. 페이지 초기화
// ==========================================

document.addEventListener('DOMContentLoaded', function() {
    // URL에서 review_id 추출
    const pathParts = window.location.pathname.split('/');
    currentReviewId = pathParts[pathParts.length - 1];

    if (currentReviewId) {
        document.getElementById('reviewIdDisplay').textContent = currentReviewId;
        loadReviewData();
    }
});

// ==========================================
// 2. 데이터 로드
// ==========================================

async function loadReviewData() {
    try {
        // 기본 리뷰 데이터 로드
        const response = await fetch(`/api/phase4/review/${currentReviewId}`);
        if (!response.ok) throw new Error('리뷰 데이터 로드 실패');

        currentData = await response.json();
        populateBasicInfo(currentData);

        // 콘텐츠 생성 데이터 로드
        const contentResponse = await fetch(`/api/phase1/review/${currentReviewId}/content`);
        if (contentResponse.ok) {
            const contentData = await contentResponse.json();
            if (contentData.status === 'success') {
                populateContentData(contentData.data);
            }
        }

    } catch (error) {
        console.error('데이터 로드 오류:', error);
        alert('데이터 로드 중 오류가 발생했습니다.');
    }
}

// ==========================================
// 3. UI 채우기 - 기본 정보
// ==========================================

function populateBasicInfo(data) {
    // Section 1: 소싱 정보
    const sourceData = data.source_data || {};

    document.getElementById('sourceUrl').value = sourceData.source_url || data.source_url || '-';
    document.getElementById('sourceUrlLink').href = sourceData.source_url || data.source_url || '#';
    document.getElementById('sourceTitle').value = data.source_title || '-';
    document.getElementById('sourceCategory').value = sourceData.category || data.category || '-';
    document.getElementById('sourcePriceCny').value = sourceData.source_price_cny || '-';
    document.getElementById('sourceWeight').value = sourceData.weight_kg || '-';
    document.getElementById('sourcingDecision').value = data.decision || sourceData.sourcing_decision || '-';
    document.getElementById('reviewScore').value = data.score || '-';

    // Section 4: 채널 기본 등록 정보
    document.getElementById('naverTitle').value = data.reviewed_naver_title || data.generated_naver_title || '';
    document.getElementById('naverDescription').value = data.reviewed_naver_description || data.generated_naver_description || '';
    document.getElementById('coupangTitle').value = data.reviewed_coupang_title || data.generated_coupang_title || '';
    document.getElementById('generatedPrice').value = data.reviewed_price || data.generated_price || '';

    // Section 9: 워크플로우 정보
    document.getElementById('reviewStatus').value = data.review_status || 'draft';
    document.getElementById('lastUpdated').value = data.updated_at || '-';
    document.getElementById('reviewNotes').value = data.review_notes || '';
}

// ==========================================
// 4. UI 채우기 - 콘텐츠 데이터
// ==========================================

function populateContentData(data) {
    // Section 2: 리스크 평가
    if (data.risk_assessment) {
        const risk = data.risk_assessment;
        document.getElementById('riskFinalDecision').value = risk.final_decision || '';
        document.getElementById('riskLevel').value = risk.risk_level || '';
        document.getElementById('riskIpNotes').value = risk.ip_notes || '';
        document.getElementById('riskClaimNotes').value = risk.claim_notes || '';
        document.getElementById('riskComplianceNotes').value = risk.compliance_notes || '';
    }

    // Section 3: 상품 핵심 요약
    if (data.summary) {
        const summary = data.summary;
        document.getElementById('positioningSummary').value = summary.positioning_summary || '';
        document.getElementById('uspPoints').value = arrayToLines(summary.usp_points);
        document.getElementById('targetCustomer').value = summary.target_customer || '';
        document.getElementById('usageScenarios').value = arrayToLines(summary.usage_scenarios);
        document.getElementById('differentiationPoints').value = arrayToLines(summary.differentiation_points);
        document.getElementById('searchIntentSummary').value = summary.search_intent_summary || '';
    }

    // Section 5: 상세페이지 콘텐츠
    if (data.detail_content) {
        const detail = data.detail_content;
        document.getElementById('mainTitle').value = detail.main_title || '';
        document.getElementById('hookCopies').value = arrayToLines(detail.hook_copies);
        document.getElementById('keyBenefits').value = arrayToLines(detail.key_benefits);
        document.getElementById('problemScenarios').value = arrayToLines(detail.problem_scenarios);
        document.getElementById('solutionNarrative').value = detail.solution_narrative || '';
        document.getElementById('usageGuide').value = detail.usage_guide || '';
        document.getElementById('cautions').value = detail.cautions || '';
        document.getElementById('faq').value = faqToText(detail.faq);
        document.getElementById('naverBody').value = detail.naver_body || '';
        document.getElementById('coupangBody').value = detail.coupang_body || '';
        document.getElementById('shortAdCopies').value = arrayToLines(detail.short_ad_copies);
    }

    // Section 6: 이미지 리디자인 기획
    if (data.image_design) {
        const image = data.image_design;
        document.getElementById('mainThumbnailCopy').value = image.main_thumbnail_copy || '';
        document.getElementById('subThumbnailCopies').value = arrayToLines(image.sub_thumbnail_copies);
        document.getElementById('bannerCopy').value = image.banner_copy || '';
        document.getElementById('sectionCopies').value = arrayToLines(image.section_copies);
        document.getElementById('layoutGuide').value = image.layout_guide || '';
        document.getElementById('toneManner').value = image.tone_manner || '';
        document.getElementById('forbiddenExpressions').value = arrayToLines(image.forbidden_expressions);
        document.getElementById('generationPrompt').value = image.generation_prompt || '';
        document.getElementById('editPrompt').value = image.edit_prompt || '';
    }

    // Section 7: 판매 전략
    if (data.sales_strategy) {
        const strategy = data.sales_strategy;
        document.getElementById('targetAudience').value = strategy.target_audience || '';
        document.getElementById('adPoints').value = arrayToLines(strategy.ad_points);
        document.getElementById('primaryKeywords').value = arrayToCommas(strategy.primary_keywords);
        document.getElementById('secondaryKeywords').value = arrayToCommas(strategy.secondary_keywords);
        document.getElementById('hashtags').value = arrayToCommas(strategy.hashtags);
        document.getElementById('reviewPoints').value = arrayToLines(strategy.review_points);
        document.getElementById('pricePositioning').value = strategy.price_positioning || '';
        document.getElementById('salesChannels').value = arrayToCommas(strategy.sales_channels);
        document.getElementById('competitiveAngles').value = arrayToLines(strategy.competitive_angles);
    }

    // Section 10: 생성 정보
    document.getElementById('contentGeneratedAt').value = data.generated_at || '-';
    document.getElementById('contentReviewer').value = data.reviewer || '-';
}

// ==========================================
// 5. 헬퍼 함수
// ==========================================

function arrayToLines(arr) {
    if (!arr || !Array.isArray(arr)) return '';
    return arr.map(item => `- ${item}`).join('\n');
}

function arrayToCommas(arr) {
    if (!arr || !Array.isArray(arr)) return '';
    return arr.join(', ');
}

function faqToText(faqArray) {
    if (!faqArray || !Array.isArray(faqArray)) return '';
    return faqArray.map(item => `Q: ${item.q}\nA: ${item.a}`).join('\n\n');
}

function linesToArray(text) {
    if (!text) return [];
    return text.split('\n')
        .map(line => line.trim().replace(/^-\s*/, ''))
        .filter(line => line.length > 0);
}

function commasToArray(text) {
    if (!text) return [];
    return text.split(',')
        .map(item => item.trim())
        .filter(item => item.length > 0);
}

function textToFaq(text) {
    if (!text) return [];
    const pairs = text.split('\n\n');
    const faq = [];

    for (const pair of pairs) {
        const lines = pair.split('\n').filter(l => l.trim());
        if (lines.length >= 2) {
            const q = lines[0].replace(/^Q:\s*/, '').trim();
            const a = lines[1].replace(/^A:\s*/, '').trim();
            if (q && a) {
                faq.push({ q, a });
            }
        }
    }

    return faq;
}

// ==========================================
// 6. 콘텐츠 생성 함수들
// ==========================================

async function generateSummary() {
    await generateContent('summary', '/api/phase1/review/' + currentReviewId + '/generate-summary');
}

async function generateDetailContent() {
    await generateContent('detail', '/api/phase1/review/' + currentReviewId + '/generate-detail-content');
}

async function generateImageDesign() {
    await generateContent('image_design', '/api/phase1/review/' + currentReviewId + '/generate-image-design');
}

async function generateSalesStrategy() {
    await generateContent('sales_strategy', '/api/phase1/review/' + currentReviewId + '/generate-sales-strategy');
}

async function generateRiskAssessment() {
    // 리스크는 전체 생성 시에만 포함되도록
    await generateAllContent();
}

async function generateAllContent() {
    const confirmed = confirm('모든 콘텐츠를 생성하시겠습니까? (기존 내용이 덮어써집니다)');
    if (!confirmed) return;

    await generateContent('all', '/api/phase1/review/' + currentReviewId + '/generate-all');
}

async function generateContent(type, endpoint) {
    try {
        // 버튼 비활성화 및 로딩 표시
        showLoading(type);

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ regenerate: true })
        });

        if (!response.ok) throw new Error('콘텐츠 생성 실패');

        const result = await response.json();

        if (result.status === 'success') {
            // UI 업데이트
            if (type === 'all') {
                populateContentData({
                    summary: result.data.summary,
                    detail_content: result.data.detail_content,
                    image_design: result.data.image_design,
                    sales_strategy: result.data.sales_strategy,
                    risk_assessment: result.data.risk_assessment
                });
            } else {
                const dataKey = type === 'summary' ? 'summary' :
                               type === 'detail' ? 'detail_content' :
                               type === 'image_design' ? 'image_design' :
                               'sales_strategy';
                populateContentData({ [dataKey]: result.data });
            }

            alert('콘텐츠가 생성되었습니다.');
        } else {
            throw new Error(result.message || '생성 실패');
        }

    } catch (error) {
        console.error('콘텐츠 생성 오류:', error);
        alert('콘텐츠 생성 중 오류가 발생했습니다: ' + error.message);
    } finally {
        hideLoading(type);
    }
}

function showLoading(type) {
    // 로딩 표시 구현 (선택사항)
    console.log('Loading:', type);
}

function hideLoading(type) {
    // 로딩 숨김 구현 (선택사항)
    console.log('Loaded:', type);
}

// ==========================================
// 7. 저장 및 워크플로우 함수들
// ==========================================

async function saveAllContent() {
    try {
        // 모든 필드 수집
        const payload = {
            // 채널 기본 정보
            reviewed_naver_title: document.getElementById('naverTitle').value,
            reviewed_naver_description: document.getElementById('naverDescription').value,
            reviewed_coupang_title: document.getElementById('coupangTitle').value,
            reviewed_price: parseFloat(document.getElementById('generatedPrice').value) || null,

            // 리스크 평가
            risk_assessment: {
                final_decision: document.getElementById('riskFinalDecision').value,
                risk_level: document.getElementById('riskLevel').value,
                ip_notes: document.getElementById('riskIpNotes').value,
                claim_notes: document.getElementById('riskClaimNotes').value,
                compliance_notes: document.getElementById('riskComplianceNotes').value
            },

            // 상품 요약
            product_summary: {
                positioning_summary: document.getElementById('positioningSummary').value,
                usp_points: linesToArray(document.getElementById('uspPoints').value),
                target_customer: document.getElementById('targetCustomer').value,
                usage_scenarios: linesToArray(document.getElementById('usageScenarios').value),
                differentiation_points: linesToArray(document.getElementById('differentiationPoints').value),
                search_intent_summary: document.getElementById('searchIntentSummary').value
            },

            // 상세 콘텐츠
            detail_content: {
                main_title: document.getElementById('mainTitle').value,
                hook_copies: linesToArray(document.getElementById('hookCopies').value),
                key_benefits: linesToArray(document.getElementById('keyBenefits').value),
                problem_scenarios: linesToArray(document.getElementById('problemScenarios').value),
                solution_narrative: document.getElementById('solutionNarrative').value,
                usage_guide: document.getElementById('usageGuide').value,
                cautions: document.getElementById('cautions').value,
                faq: textToFaq(document.getElementById('faq').value),
                naver_body: document.getElementById('naverBody').value,
                coupang_body: document.getElementById('coupangBody').value,
                short_ad_copies: linesToArray(document.getElementById('shortAdCopies').value)
            },

            // 이미지 디자인
            image_design: {
                main_thumbnail_copy: document.getElementById('mainThumbnailCopy').value,
                sub_thumbnail_copies: linesToArray(document.getElementById('subThumbnailCopies').value),
                banner_copy: document.getElementById('bannerCopy').value,
                section_copies: linesToArray(document.getElementById('sectionCopies').value),
                layout_guide: document.getElementById('layoutGuide').value,
                tone_manner: document.getElementById('toneManner').value,
                forbidden_expressions: linesToArray(document.getElementById('forbiddenExpressions').value),
                generation_prompt: document.getElementById('generationPrompt').value,
                edit_prompt: document.getElementById('editPrompt').value
            },

            // 판매 전략
            sales_strategy: {
                target_audience: document.getElementById('targetAudience').value,
                ad_points: linesToArray(document.getElementById('adPoints').value),
                primary_keywords: commasToArray(document.getElementById('primaryKeywords').value),
                secondary_keywords: commasToArray(document.getElementById('secondaryKeywords').value),
                hashtags: commasToArray(document.getElementById('hashtags').value),
                review_points: linesToArray(document.getElementById('reviewPoints').value),
                price_positioning: document.getElementById('pricePositioning').value,
                sales_channels: commasToArray(document.getElementById('salesChannels').value),
                competitive_angles: linesToArray(document.getElementById('competitiveAngles').value)
            },

            review_notes: document.getElementById('reviewNotes').value
        };

        // 기존 save API 사용
        const response = await fetch(`/api/phase4/review/${currentReviewId}/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('저장 실패');

        alert('저장되었습니다.');

    } catch (error) {
        console.error('저장 오류:', error);
        alert('저장 중 오류가 발생했습니다: ' + error.message);
    }
}

async function holdReview() {
    if (!confirm('보류하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/phase4/review/${currentReviewId}/hold`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reviewed_by: 'operator',
                review_notes: document.getElementById('reviewNotes').value
            })
        });

        if (!response.ok) throw new Error('보류 처리 실패');

        alert('보류 처리되었습니다.');
        loadReviewData();

    } catch (error) {
        alert('보류 처리 중 오류: ' + error.message);
    }
}

async function rejectReview() {
    if (!confirm('거부하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/phase4/review/${currentReviewId}/reject`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reviewed_by: 'operator',
                review_notes: document.getElementById('reviewNotes').value
            })
        });

        if (!response.ok) throw new Error('거부 처리 실패');

        alert('거부 처리되었습니다.');
        loadReviewData();

    } catch (error) {
        alert('거부 처리 중 오류: ' + error.message);
    }
}

async function approveForExport() {
    if (!confirm('내보내기 승인하시겠습니까?')) return;

    try {
        const response = await fetch(`/api/phase4/review/${currentReviewId}/approve-export`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reviewed_by: 'operator',
                review_notes: document.getElementById('reviewNotes').value
            })
        });

        if (!response.ok) throw new Error('승인 처리 실패');

        alert('내보내기 승인되었습니다.');
        loadReviewData();

    } catch (error) {
        alert('승인 처리 중 오류: ' + error.message);
    }
}

async function exportToNaverCSV() {
    try {
        const response = await fetch('/api/phase4/review/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                review_ids: [currentReviewId],
                channel: 'naver',
                exported_by: 'operator'
            })
        });

        if (!response.ok) throw new Error('CSV 생성 실패');

        const result = await response.json();

        // CSV 다운로드
        const blob = new Blob([result.csv_data], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = result.filename;
        link.click();

    } catch (error) {
        alert('네이버 CSV 생성 중 오류: ' + error.message);
    }
}

async function exportToCoupangCSV() {
    try {
        const response = await fetch('/api/phase4/review/export/csv', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                review_ids: [currentReviewId],
                channel: 'coupang',
                exported_by: 'operator'
            })
        });

        if (!response.ok) throw new Error('CSV 생성 실패');

        const result = await response.json();

        // CSV 다운로드
        const blob = new Blob([result.csv_data], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = result.filename;
        link.click();

    } catch (error) {
        alert('쿠팡 CSV 생성 중 오류: ' + error.message);
    }
}
