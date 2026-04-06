/**
 * FORTIMOVE Sourcing - Content Script
 * 현재 페이지에서 상품 정보를 추출합니다.
 */

(function() {
    'use strict';

    // 플랫폼 식별
    function detectPlatform() {
        const host = location.hostname.toLowerCase();
        if (host.includes('iherb.com')) return 'iherb';
        if (host.includes('amazon.')) return 'amazon';
        if (host.includes('taobao.com')) return 'taobao';
        if (host.includes('tmall.com')) return 'tmall';
        if (host.includes('1688.com')) return '1688';
        if (host.includes('rakuten.co.jp')) return 'rakuten';
        return 'unknown';
    }

    // 국가 추론
    function detectCountry(platform) {
        const host = location.hostname.toLowerCase();
        if (platform === 'iherb') {
            if (host.startsWith('jp.')) return 'JP';
            if (host.startsWith('kr.')) return 'KR';
            return 'US';
        }
        if (platform === 'amazon') {
            if (host.includes('.co.jp')) return 'JP';
            if (host.includes('.co.uk')) return 'GB';
            return 'US';
        }
        if (platform === 'rakuten') return 'JP';
        if (['taobao', 'tmall', '1688'].includes(platform)) return 'CN';
        return 'US';
    }

    // JSON-LD 파싱 (iHerb 주력)
    function extractFromJsonLd() {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const script of scripts) {
            try {
                const data = JSON.parse(script.textContent);
                const items = Array.isArray(data) ? data : [data];
                for (const item of items) {
                    if (item['@type'] === 'Product' || item['@type'] === 'IndividualProduct') {
                        return item;
                    }
                }
            } catch (e) { /* skip */ }
        }
        return null;
    }

    // ── 플랫폼별 추출기 ──────────────────────

    function extractIHerb() {
        const data = { platform: 'iherb' };
        const jsonLd = extractFromJsonLd();

        if (jsonLd) {
            data.title = jsonLd.name || '';
            data.brand = (jsonLd.brand?.name || jsonLd.brand || '').toString();
            data.description = (jsonLd.description || '').substring(0, 500);
            const cat = jsonLd.category;
            if (typeof cat === 'object') data.category = cat?.name || '';
            else if (typeof cat === 'string') data.category = cat;
            const imgs = jsonLd.image;
            data.images = Array.isArray(imgs) ? imgs : (imgs ? [imgs] : []);
            const offers = jsonLd.offers;
            if (offers) {
                data.price = offers.price || offers.lowPrice || '';
                data.currency = offers.priceCurrency || '';
            }
        }

        // DOM 폴백
        if (!data.title) data.title = document.querySelector('h1#name, h1.product-name, h1')?.textContent?.trim() || document.title;
        if (!data.brand) data.brand = document.querySelector('#brand a, .product-brand a, [itemprop="brand"]')?.textContent?.trim() || '';
        if (!data.price) data.price = document.querySelector('#price, .price-inner-text, [itemprop="price"]')?.textContent?.trim() || '';

        // 이미지 DOM 보강
        if (!data.images || data.images.length < 3) {
            const imgSet = new Set(data.images || []);
            document.querySelectorAll('img').forEach(img => {
                const src = img.getAttribute('src') || img.getAttribute('data-src') || '';
                if (src.includes('cloudinary') && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                    imgSet.add(src);
                }
            });
            data.images = Array.from(imgSet).slice(0, 10);
        }

        return data;
    }

    function extractAmazon() {
        const data = { platform: 'amazon' };

        data.title = document.querySelector('#productTitle')?.textContent?.trim() || document.querySelector('h1')?.textContent?.trim() || '';

        const byline = document.querySelector('#bylineInfo');
        if (byline) {
            data.brand = byline.textContent.trim().replace(/^Visit the\s*/i, '').replace(/\s*Store$/i, '').replace(/^Brand:\s*/i, '');
        }

        // 카테고리 (brodcrumb)
        const crumbs = document.querySelectorAll('#wayfinding-breadcrumbs_feature_div a');
        if (crumbs.length > 0) {
            data.category = crumbs[crumbs.length - 1].textContent.trim();
        }

        // 가격
        data.price = document.querySelector('.a-price .a-offscreen')?.textContent?.trim() ||
                     document.querySelector('#priceblock_ourprice')?.textContent?.trim() || '';

        // 이미지 — hiRes 패턴에서 추출
        const imgSet = new Set();
        const html = document.documentElement.outerHTML;
        const hiResMatches = html.match(/"hiRes":"(https:\/\/[^"]+\.(?:jpg|jpeg|png))"/g) || [];
        hiResMatches.forEach(m => {
            const url = m.match(/"hiRes":"(https:\/\/[^"]+)"/)?.[1];
            if (url) imgSet.add(url.replace(/\\u002F/g, '/'));
        });
        // DOM 이미지
        document.querySelectorAll('#altImages img, #imgTagWrapperId img, #landingImage').forEach(img => {
            const src = img.getAttribute('data-old-hires') || img.getAttribute('src') || '';
            if (src.includes('media-amazon') && /\.(jpg|jpeg|png)/i.test(src)) {
                imgSet.add(src);
            }
        });
        data.images = Array.from(imgSet).slice(0, 10);

        // 설명
        const feature = document.querySelector('#feature-bullets ul');
        if (feature) {
            data.description = Array.from(feature.querySelectorAll('li')).map(li => li.textContent.trim()).join(' ').substring(0, 500);
        }

        return data;
    }

    // 무효 타이틀 필터 (타오바오/티몰 공통)
    const TAOBAO_BAD_TITLES = ['按图片搜索', '搜索', '图片', '상품검색', 'search', '登录', '注册', '购物车', '首页', '我的淘宝', '淘宝', '天猫'];
    function isBadTaobaoTitle(t) {
        if (!t || t.trim().length < 10) return true;
        const trimmed = t.trim();
        return TAOBAO_BAD_TITLES.some(b => trimmed === b || trimmed.length < 8);
    }

    // 이미지 URL 정규화 (타오바오/알리바바 CDN)
    function normalizeTaobaoImg(src) {
        if (!src) return '';
        if (src.startsWith('//')) src = 'https:' + src;
        // _400x400.jpg, _250x250q90.jpg 등 썸네일 → 원본
        src = src.replace(/_\d+x\d+[^./]*\.(jpg|jpeg|png|webp)/i, '.$1');
        // .jpg_Q90.webp → .jpg
        src = src.replace(/\.(jpg|jpeg|png)_[^.]+\.(webp|jpg)/i, '.$1');
        return src;
    }

    function extractTaobao() {
        const data = { platform: 'taobao' };

        // ── 1. 타이틀 추출 (여러 경로) ──
        // a) window 객체에서 (타오바오는 __INIT_DATA__ 또는 globalData에 상품 정보 저장)
        let jsTitle = '';
        try {
            const candidates = [
                window.runParams?.data?.item?.title,
                window.g_config?.itemDO?.title,
                window.__INIT_DATA__?.item?.title,
                window.__DATA__?.item?.title,
            ];
            for (const c of candidates) {
                if (c && !isBadTaobaoTitle(c)) { jsTitle = c; break; }
            }
        } catch (e) {}

        // b) 스크립트 텍스트 파싱
        if (!jsTitle) {
            try {
                const scripts = document.querySelectorAll('script');
                for (const s of scripts) {
                    const text = s.textContent || '';
                    if (text.length < 100) continue;
                    // 다양한 패턴
                    const patterns = [
                        /"itemTitle"\s*:\s*"([^"]{15,300})"/,
                        /"title"\s*:\s*"([^"]{15,300})"/,
                        /"subtitle"\s*:\s*"([^"]{15,300})"/,
                        /"itemName"\s*:\s*"([^"]{15,300})"/,
                    ];
                    for (const p of patterns) {
                        const m = text.match(p);
                        if (m) {
                            const candidate = m[1].replace(/\\u002F/g, '/').replace(/\\"/g, '"');
                            if (!isBadTaobaoTitle(candidate)) {
                                jsTitle = candidate;
                                break;
                            }
                        }
                    }
                    if (jsTitle) break;
                }
            } catch (e) {}
        }

        // c) DOM 셀렉터 (다중 시도)
        const domSelectors = [
            '.tb-main-title[data-title]', // data-title 속성
            '[class*="ItemTitle--mainTitle"]',
            '[class*="mainTitle--"]',
            '.tb-detail-hd h1',
            '#J_Title h1',
            '.tm-title',
            '[class*="itemTitle"]',
        ];
        let domTitle = '';
        for (const sel of domSelectors) {
            const el = document.querySelector(sel);
            if (el) {
                domTitle = el.getAttribute('data-title') || el.textContent?.trim() || '';
                if (!isBadTaobaoTitle(domTitle)) break;
                domTitle = '';
            }
        }

        // d) 메타태그
        const metaTitle = document.querySelector('meta[property="og:title"]')?.content ||
                          document.querySelector('meta[name="keywords"]')?.content || '';

        // 우선순위: JS > DOM > meta > document.title
        const titleCandidates = [jsTitle, domTitle, metaTitle, document.title];
        data.title = titleCandidates.find(t => !isBadTaobaoTitle(t)) || document.title;

        // ── 2. 가격 추출 ──
        const priceSelectors = [
            '[class*="Price--priceText"]',
            '[class*="price--"] [class*="unit"]',
            '.tm-price',
            '.tb-rmb-num',
            '[class*="price"] strong',
            'em[class*="price"]',
            '.tb-promo-price .tb-rmb-num',
        ];
        for (const sel of priceSelectors) {
            const el = document.querySelector(sel);
            if (el) {
                const t = el.textContent?.trim();
                if (t && /\d/.test(t)) {
                    data.price = t.startsWith('¥') ? t : '¥' + t;
                    break;
                }
            }
        }

        // ── 3. 브랜드 ──
        data.brand = document.querySelector('[class*="brandName"], .brand a, [class*="brand"] a, [class*="Brand--brandName"]')?.textContent?.trim() || '';

        // ── 4. 이미지 수집 (3단계) ──
        const imgSet = new Set();

        // 4-a. 메인 상품 이미지 (상단 갤러리)
        const mainImgSelectors = [
            '#J_UlThumb img',       // 타오바오 썸네일
            '#J_ImgBooth',           // 타오바오 메인
            '.tb-gallery img',
            '[class*="PicGallery"] img',
            '[class*="thumbnail"] img',
        ];
        mainImgSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(img => {
                const src = normalizeTaobaoImg(img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-ks-lazyload') || '');
                if ((src.includes('alicdn') || src.includes('taobaocdn')) && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                    imgSet.add(src);
                }
            });
        });

        // 4-b. 상세페이지 영역 타겟팅 (핵심!)
        // 타오바오는 #J_DivItemDesc, 티몰은 #description, .tm-detail-desc 등
        const descSelectors = [
            '#J_DivItemDesc',
            '#description',
            '.tm-detail-desc',
            '#detail',
            '[class*="descModule"]',
            '[class*="Desc--container"]',
            '#J_RichTextWrapper',
            '.J_DetailWrap',
        ];
        for (const sel of descSelectors) {
            const container = document.querySelector(sel);
            if (container) {
                container.querySelectorAll('img').forEach(img => {
                    const src = normalizeTaobaoImg(
                        img.getAttribute('src') ||
                        img.getAttribute('data-src') ||
                        img.getAttribute('data-ks-lazyload') ||
                        img.getAttribute('data-lazysrc') || ''
                    );
                    if ((src.includes('alicdn') || src.includes('taobaocdn')) && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                        imgSet.add(src);
                    }
                });
            }
        }

        // 4-c. 전체 페이지 폴백 (alicdn 이미지 전부)
        document.querySelectorAll('img').forEach(img => {
            // 너무 작은 아이콘은 제외 (아이콘, UI)
            const w = img.naturalWidth || parseInt(img.getAttribute('width')) || 0;
            const h = img.naturalHeight || parseInt(img.getAttribute('height')) || 0;
            if (w > 0 && w < 100) return;  // 100px 미만 UI 아이콘 제외

            const src = normalizeTaobaoImg(
                img.getAttribute('src') ||
                img.getAttribute('data-src') ||
                img.getAttribute('data-ks-lazyload') ||
                img.getAttribute('data-lazysrc') || ''
            );
            if ((src.includes('alicdn') || src.includes('taobaocdn')) && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                // UI 이미지 필터 (작은 아이콘, 로고 등)
                if (src.includes('tps/i') || src.includes('assets')) return;  // 타오바오 UI 리소스
                imgSet.add(src);
            }
        });

        data.images = Array.from(imgSet).slice(0, 50);

        return data;
    }

    // 타오바오/티몰 자동 스크롤 (lazy load 이미지 로드)
    async function autoScrollTaobao() {
        return new Promise((resolve) => {
            const originalScroll = window.scrollY;
            let currentScroll = 0;
            const scrollStep = 500;
            const maxScroll = Math.max(document.body.scrollHeight, 15000);
            const interval = setInterval(() => {
                window.scrollTo(0, currentScroll);
                currentScroll += scrollStep;
                if (currentScroll >= maxScroll) {
                    clearInterval(interval);
                    // 맨 위로 복귀 대신 맨 아래에 머물러서 모든 이미지 로드 상태 유지
                    setTimeout(() => {
                        window.scrollTo(0, originalScroll);
                        resolve();
                    }, 800);
                }
            }, 150);
        });
    }

    function extract1688() {
        const data = { platform: '1688' };

        // 타이틀
        const titleSelectors = [
            '.d-title',
            '.title-container h1',
            '[class*="title-container"]',
            '[class*="mod-detail-title"] h1',
            'h1',
        ];
        for (const sel of titleSelectors) {
            const el = document.querySelector(sel);
            if (el) {
                const t = el.textContent?.trim();
                if (t && t.length >= 10 && !isBadTaobaoTitle(t)) {
                    data.title = t;
                    break;
                }
            }
        }
        if (!data.title) data.title = document.title;

        // 가격
        const priceSelectors = [
            '.mod-detail-price [class*="price-num"]',
            '.price [class*="value"]',
            '.mod-price [class*="num"]',
            '[class*="price"] em',
        ];
        for (const sel of priceSelectors) {
            const el = document.querySelector(sel);
            if (el) {
                const t = el.textContent?.trim();
                if (t && /\d/.test(t)) {
                    data.price = t.startsWith('¥') ? t : '¥' + t;
                    break;
                }
            }
        }

        // 이미지 (상세 영역 + 전체 alicdn)
        const imgSet = new Set();

        // 상세 영역
        const descSelectors = ['#desc-lazyload-container', '.content-detail', '.mod-detail-description', '[class*="richTextContainer"]'];
        for (const sel of descSelectors) {
            const container = document.querySelector(sel);
            if (container) {
                container.querySelectorAll('img').forEach(img => {
                    const src = normalizeTaobaoImg(img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazyload-src') || '');
                    if (src.includes('alicdn') && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                        imgSet.add(src);
                    }
                });
            }
        }

        // 전체 폴백
        document.querySelectorAll('img').forEach(img => {
            const w = img.naturalWidth || parseInt(img.getAttribute('width')) || 0;
            if (w > 0 && w < 100) return;
            const src = normalizeTaobaoImg(img.getAttribute('src') || img.getAttribute('data-src') || img.getAttribute('data-lazyload-src') || '');
            if (src.includes('alicdn') && /\.(jpg|jpeg|png|webp)/i.test(src)) {
                if (src.includes('tps/i') || src.includes('assets')) return;
                imgSet.add(src);
            }
        });

        data.images = Array.from(imgSet).slice(0, 50);
        data.brand = document.querySelector('[class*="brand"], .supplier-name, .company-name')?.textContent?.trim() || '';
        return data;
    }

    function extractRakuten() {
        const data = { platform: 'rakuten' };
        data.title = document.querySelector('.item_name, h1')?.textContent?.trim() || document.title;
        data.price = document.querySelector('.item_current_price, [class*="price"]')?.textContent?.trim() || '';
        data.brand = document.querySelector('.item_shopname, [class*="shop"]')?.textContent?.trim() || '';

        const imgSet = new Set();
        document.querySelectorAll('img').forEach(img => {
            const src = img.getAttribute('src') || '';
            if ((src.includes('rakuten.co.jp') || src.includes('r.r10s.jp')) && /\.(jpg|jpeg|png)/i.test(src)) {
                imgSet.add(src);
            }
        });
        data.images = Array.from(imgSet).slice(0, 10);
        return data;
    }

    // ── 메인 추출 함수 ──────────────────────

    function extractProduct() {
        const platform = detectPlatform();
        const country = detectCountry(platform);

        let data;
        switch (platform) {
            case 'iherb': data = extractIHerb(); break;
            case 'amazon': data = extractAmazon(); break;
            case 'taobao':
            case 'tmall': data = extractTaobao(); break;
            case '1688': data = extract1688(); break;
            case 'rakuten': data = extractRakuten(); break;
            default: data = { platform, title: document.title, images: [] };
        }

        // 공통 정보 추가
        data.url = location.href;
        data.country = country;
        data.extracted_at = new Date().toISOString();

        // OG 이미지 폴백
        if (!data.images || data.images.length === 0) {
            const og = document.querySelector('meta[property="og:image"]')?.content;
            if (og) data.images = [og];
        }

        // 설명 폴백
        if (!data.description) {
            data.description = document.querySelector('meta[property="og:description"]')?.content ||
                               document.querySelector('meta[name="description"]')?.content || '';
        }

        // 데이터 정리
        if (data.title) data.title = data.title.substring(0, 300);
        if (data.brand) data.brand = data.brand.substring(0, 100);
        if (data.description) data.description = data.description.substring(0, 1000);

        return data;
    }

    // ── 메시지 리스너 ──────────────────────

    chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        if (msg.action === 'extract') {
            const platform = detectPlatform();

            // 타오바오/티몰/1688은 자동 스크롤 후 추출 (lazy load 로드)
            if (['taobao', 'tmall', '1688'].includes(platform)) {
                (async () => {
                    try {
                        await autoScrollTaobao();
                        const data = extractProduct();
                        sendResponse({ success: true, data: data, scrolled: true });
                    } catch (e) {
                        sendResponse({ success: false, error: e.message });
                    }
                })();
                return true; // 비동기 응답 유지
            }

            // 그 외 사이트는 즉시 추출
            try {
                const data = extractProduct();
                sendResponse({ success: true, data: data });
            } catch (e) {
                sendResponse({ success: false, error: e.message });
            }
            return true;
        }
    });

    // 배지 업데이트 (페이지 로드 시 자동 추출 가능 여부)
    chrome.runtime.sendMessage({ action: 'page_ready', platform: detectPlatform() });
})();
