"""
소싱/상품 발굴 에이전트 (Sourcing Agent)
- 타오바오/1688 URL 분석
- 리스크 1차 필터링 (지재권/통관/의료기기)
- 벤더 질문 생성 (한국어/중국어)
- 상품 분류 (테스트/반복/PB)
"""

import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Type
from pydantic import BaseModel, Field
from anthropic import Anthropic

from agent_framework import BaseAgent, register_agent
from korean_law_helper import get_korean_law_helper

logger = logging.getLogger(__name__)

# ============================================================
# Schema Definitions
# ============================================================

class SourcingInputSchema(BaseModel):
    source_url: str                              # 타오바오/1688 URL (필수)
    keywords: Optional[List[str]] = Field(default_factory=list)     # 검색 키워드
    vendor_chat: Optional[str] = None            # 벤더 채팅 내역
    target_category: Optional[str] = None        # 타겟 카테고리
    source_title: Optional[str] = None           # 상품 제목 (URL 파싱 대신 직접 제공 가능)
    source_description: Optional[str] = None     # 상품 설명
    source_price_cny: Optional[float] = None     # 매입가 (위안)
    market: str = "korea"                        # 타겟 시장 (기본값: korea)

class SourcingOutputSchema(BaseModel):
    product_classification: str                  # 테스트/반복/PB
    vendor_questions_ko: List[str]               # 한국어 질문
    vendor_questions_zh: List[str]               # 중국어 질문
    sourcing_decision: str                       # 통과/보류/제외
    risk_flags: List[str]                        # 리스크 플래그
    risk_details: Dict[str, Any]                 # 리스크 상세 정보
    next_step_recommendation: str                # 다음 단계 권고
    extracted_info: Dict[str, Any]               # URL에서 추출한 정보
    legal_check: Optional[Dict[str, Any]] = None # 법령 검증 결과 (Korean Law MCP)

# ============================================================
# Sourcing Agent Implementation
# ============================================================

@register_agent("sourcing")
class SourcingAgent(BaseAgent):
    @property
    def input_schema(self) -> Type[BaseModel]:
        return SourcingInputSchema

    @property
    def output_schema(self) -> Type[BaseModel]:
        return SourcingOutputSchema

    def __init__(self):
        super().__init__("sourcing")
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("Sourcing Agent initiated without ANTHROPIC_API_KEY")

        self.model = "claude-sonnet-4-20250514"

        # ⚠️ 2026-04-01 추가: Korean Law MCP 헬퍼 초기화
        self.korean_law = get_korean_law_helper()
        if self.korean_law.available:
            logger.info("Korean Law MCP 연동 완료")
        else:
            logger.warning("Korean Law MCP 사용 불가 (키워드 필터만 사용)")

        # ========================================================
        # Compliance 필수 체크: 2026년 8월 관세법 개정 + 4월 KC 인증 규제
        # ========================================================
        self.risk_keywords = {
            "지재권": [
                "나이키", "아디다스", "샤넬", "구찌", "루이비통", "애플", "삼성",
                "아이폰", "갤럭시", "nike", "adidas", "chanel", "gucci", "apple",
                "디즈니", "마블", "pokemon", "포켓몬", "짱구", "캐릭터"
            ],
            # ⚠️ 2026-04-01 업데이트: 의약품 별도 카테고리 분리 (약사법 준수)
            "의약품": [
                "의약품", "다이어트약", "피임약", "슬리밍", "한약재", "당귀", "인삼",
                "수면제", "진통제", "식욕억제", "지방분해", "체중감량", "살빠지는",
                "약", "medicine", "drug", "diet pill", "sleeping pill", "painkiller",
                "처방전", "복용", "투약", "약효", "부작용"
            ],
            "통관": [
                "건강기능식품", "보조제", "영양제", "비타민",
                "supplement", "vitamin", "프로바이오틱스", "오메가3",
                "콜라겐", "단백질", "프로틴"
            ],
            # ⚠️ 2026-04-01 업데이트: 의료기기 키워드 대폭 강화 (의료기기법 준수)
            "의료기기": [
                "치료", "완치", "재생", "혈압", "혈당", "진단", "의료용",
                "medical", "therapy", "cure", "측정기", "모니터링", "검사",
                "레이저", "초음파", "전기자극",
                # 2026-04-01 추가: 전기/물리 치료기기
                "전기 마사지", "저주파 치료", "고주파 치료", "적외선 램프",
                "혈액순환 개선", "체지방 측정", "근육 자극", "물리치료",
                "EMS", "TENS", "저주파", "고주파", "혈행개선",
                # 2026-04-01 추가: 미용 의료기기
                "피부 재생", "주름 개선 기기", "리프팅 기기", "셀룰라이트",
                "RF", "radio frequency", "갈바닉", "초음파 리프팅",
                # 2026-04-01 추가: 가정용 의료기기
                "체온계", "혈압계", "혈당측정기", "산소포화도", "심박수",
                "nebulizer", "흡입기", "적외선 체온계"
            ],
            # 2026년 8월 관세법 개정: 간이통관 면세 한도 하향 (리스크 품목)
            "고가품_관세주의": [
                "명품", "시계", "가방", "지갑", "귀금속", "보석", "다이아몬드",
                "gold", "luxury", "premium brand"
            ],
            # 2026년 4월 KC 인증 강화: 전자제품 필수 인증
            "KC인증필수": [
                "전자제품", "배터리", "충전기", "어댑터", "전원", "무선",
                "bluetooth", "usb", "전기", "전압", "리튬", "lithium",
                "이어폰", "헤드폰", "스피커", "led", "램프", "조명"
            ],
            # 식품 안전 강화 (수입식품 안전관리)
            "식품안전": [
                "식품", "음료", "간식", "과자", "food", "snack", "drink",
                "차", "tea", "커피", "coffee", "초콜릿", "chocolate"
            ],
            # 화장품법 강화 (기능성 화장품)
            "화장품규제": [
                "미백", "주름개선", "자외선차단", "whitening", "wrinkle", "sunscreen",
                "기능성", "안티에이징", "anti-aging", "피부재생"
            ]
        }

        # 8월 관세법 개정: 간이통관 면세 한도 USD 150 → USD 100 하향
        self.customs_threshold_usd = 100  # 2026년 8월 시행

        # KC 인증 필수 품목 자동 탐지 로직 활성화
        self.kc_cert_required = True  # 2026년 4월 시행

    def _do_execute(self, input_model: SourcingInputSchema) -> Dict[str, Any]:
        """소싱 에이전트 메인 로직"""

        # 1. URL 파싱 (간단한 추출)
        extracted_info = self._extract_url_info(input_model.source_url)

        # 2. 리스크 1차 필터링 (Rule-based)
        risk_flags, risk_details = self._check_risk_keywords(
            input_model.source_title or extracted_info.get("title", ""),
            input_model.source_description or ""
        )

        # 3. LLM 기반 상세 분석
        llm_analysis = self._analyze_with_llm(input_model, risk_flags)

        # 4. 벤더 질문 생성
        vendor_questions_ko, vendor_questions_zh = self._generate_vendor_questions(
            input_model, llm_analysis
        )

        # 5. Korean Law MCP 법령 검증 (의료기기/의약품 리스크만)
        # ⚠️ 2026-04-01 추가: 법제처 API 기반 법령 확인
        legal_check = None
        if self.korean_law.available and ("의료기기" in risk_flags or "의약품" in risk_flags):
            legal_check = self._check_legal_compliance(
                input_model.source_title or "",
                input_model.source_description or "",
                risk_flags
            )

        # 6. 최종 판정
        sourcing_decision = self._make_decision(risk_flags, llm_analysis)

        # 7. 상품 분류
        product_classification = llm_analysis.get("product_classification", "테스트")

        # 8. 다음 단계 권고
        next_step = self._recommend_next_step(sourcing_decision, risk_flags)

        return {
            "product_classification": product_classification,
            "vendor_questions_ko": vendor_questions_ko,
            "vendor_questions_zh": vendor_questions_zh,
            "sourcing_decision": sourcing_decision,
            "risk_flags": risk_flags,
            "risk_details": risk_details,
            "next_step_recommendation": next_step,
            "extracted_info": extracted_info,
            "legal_check": legal_check  # Korean Law MCP 법령 검증 결과
        }

    def _extract_url_info(self, url: str) -> Dict[str, Any]:
        """URL에서 기본 정보 + 이미지 + 브랜드/카테고리/가격 추출 (Playwright)"""
        info = {
            "url": url,
            "platform": "unknown",
            "item_id": None,
            "title": None,
            "brand": None,
            "category": None,
            "price_text": None,
            "description": None,
            "images": []
        }

        # 플랫폼 식별
        url_lower = url.lower()
        if "taobao.com" in url_lower:
            info["platform"] = "taobao"
        elif "1688.com" in url_lower:
            info["platform"] = "1688"
        elif "tmall.com" in url_lower:
            info["platform"] = "tmall"
        elif "iherb.com" in url_lower:
            info["platform"] = "iherb"
        elif "amazon.com" in url_lower or "amazon.co" in url_lower:
            info["platform"] = "amazon"
        elif "rakuten.co.jp" in url_lower:
            info["platform"] = "rakuten"

        # Item ID 추출
        id_match = re.search(r'id=(\d+)', url)
        if id_match:
            info["item_id"] = id_match.group(1)

        # curl_cffi로 TLS 지문 위장 크롤링 (iHerb/Amazon 봇 차단 우회)
        html = None
        try:
            from curl_cffi import requests as cffi_requests
            r = cffi_requests.get(url, impersonate="chrome120", timeout=20, allow_redirects=True)
            # 200, 410(단종), 301 등도 HTML 내용은 사용 가능
            if r.status_code in (200, 301, 302, 410) and len(r.text) > 1000:
                html = r.text
            else:
                self.logger.warning(f"curl_cffi status {r.status_code}")
        except ImportError:
            self.logger.warning("curl_cffi 미설치 — requests 폴백")
        except Exception as e:
            self.logger.warning(f"curl_cffi 실패: {e} — requests 폴백")

        # 폴백: 일반 requests
        if not html:
            try:
                import requests
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
                }
                resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                if resp.status_code in (200, 301, 302, 410):
                    html = resp.text
            except Exception as e:
                self.logger.warning(f"requests 폴백 실패: {e}")

        # 파싱
        if html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, "html.parser")
                info.update(self._extract_from_soup(soup, info["platform"], url))
                self.logger.info(f"🖼 이미지 {len(info.get('images',[]))}개, 브랜드:{info.get('brand')}, 카테고리:{info.get('category')} / {info['platform']}")
            except Exception as e:
                self.logger.warning(f"파싱 실패: {e}")

        return info

    def _extract_from_soup(self, soup, platform: str, url: str) -> Dict[str, Any]:
        """BeautifulSoup으로 상품 정보 추출 (JSON-LD 우선)"""
        data = {}
        import json as _json

        # 0. iHerb: __NEXT_DATA__ (Next.js SSR 데이터 — 가장 정확)
        if platform == "iherb":
            try:
                next_script = soup.find("script", id="__NEXT_DATA__")
                if next_script and next_script.string:
                    nd = _json.loads(next_script.string)
                    props = nd.get("props", {}).get("pageProps", {})
                    product = props.get("product", props.get("productData", {}))
                    if not product:
                        # 중첩 구조 탐색
                        for k, v in props.items():
                            if isinstance(v, dict) and v.get("name"):
                                product = v
                                break
                    if product and isinstance(product, dict):
                        data["title"] = product.get("name", "")[:200]
                        data["brand"] = product.get("brandName", product.get("brand", ""))
                        data["description"] = product.get("description", "")[:500]
                        # 가격
                        price_val = product.get("price", product.get("discountPrice", 0))
                        currency = product.get("currency", "USD")
                        if price_val:
                            data["price_text"] = f"{currency} {price_val}"
                        # 이미지 (productImages 배열)
                        pi = product.get("images", product.get("productImages", []))
                        if isinstance(pi, list) and pi:
                            img_urls = []
                            for img_item in pi:
                                if isinstance(img_item, str):
                                    img_urls.append(img_item)
                                elif isinstance(img_item, dict):
                                    img_urls.append(img_item.get("url") or img_item.get("src") or img_item.get("large", ""))
                            img_urls = [u for u in img_urls if u and isinstance(u, str)]
                            if img_urls:
                                data["images"] = img_urls[:10]
                        # 카테고리
                        cats = product.get("categories", product.get("breadcrumbs", []))
                        if isinstance(cats, list) and cats:
                            last = cats[-1]
                            data["category"] = last.get("name", str(last)) if isinstance(last, dict) else str(last)
                        self.logger.info(f"iHerb __NEXT_DATA__ 추출 성공: {data.get('title','')[:30]}, 이미지 {len(data.get('images',[]))}장, 가격 {data.get('price_text','')}")
                        if data.get("images") and data.get("title"):
                            return data  # __NEXT_DATA__가 충분하면 바로 반환
            except Exception as e:
                self.logger.debug(f"iHerb __NEXT_DATA__ 파싱 실패: {e}")

        # 1. JSON-LD 구조화 데이터 (iHerb, Amazon 등 대부분 지원)
        try:
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    jd = _json.loads(script.string or "{}")
                except Exception:
                    continue
                items = jd if isinstance(jd, list) else [jd]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    if item.get("@type") in ("Product", "IndividualProduct"):
                        data["title"] = data.get("title") or item.get("name", "")[:200]
                        brand = item.get("brand", {})
                        if isinstance(brand, dict):
                            data["brand"] = brand.get("name")
                        elif isinstance(brand, str):
                            data["brand"] = brand
                        data["description"] = data.get("description") or (item.get("description") or "")[:500]
                        # 이미지
                        img = item.get("image")
                        imgs = []
                        if isinstance(img, list):
                            imgs = [i for i in img if isinstance(i, str)]
                        elif isinstance(img, str):
                            imgs = [img]
                        if imgs:
                            data["images"] = imgs[:10]
                        # 가격
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            price = offers.get("price") or offers.get("lowPrice")
                            currency = offers.get("priceCurrency", "")
                            if price:
                                data["price_text"] = f"{currency} {price}".strip()
                        # 카테고리 (dict/str/list 처리)
                        cat = item.get("category")
                        if isinstance(cat, dict):
                            data["category"] = cat.get("name") or cat.get("@id")
                        elif isinstance(cat, str):
                            data["category"] = cat
                        elif isinstance(cat, list) and cat:
                            first = cat[0]
                            data["category"] = first.get("name") if isinstance(first, dict) else str(first)
        except Exception as e:
            self.logger.debug(f"JSON-LD 파싱 실패: {e}")

        # 2. OG 메타태그 (폴백)
        def og(prop):
            tag = soup.find("meta", property=prop)
            return tag.get("content") if tag else None

        def meta(name):
            tag = soup.find("meta", attrs={"name": name})
            return tag.get("content") if tag else None

        if not data.get("title"):
            data["title"] = (og("og:title") or (soup.title.string if soup.title else "") or "").strip()[:200]
        if not data.get("description"):
            data["description"] = (og("og:description") or meta("description") or "").strip()[:500]
        if not data.get("images"):
            og_img = og("og:image")
            if og_img:
                data["images"] = [og_img]

        # 3-pre. Amazon은 JSON-LD 없음 — HTML 내 JSON 추출
        if platform == "amazon" and not data.get("images"):
            import re as _re
            html_str = str(soup)
            # hiRes 이미지 (Amazon 상품 상세)
            hires = _re.findall(r'"hiRes":"(https://[^"]+\.(?:jpg|jpeg|png))"', html_str)
            if hires:
                data["images"] = list(set(hires))[:10]
            # productTitle
            if not data.get("title"):
                pt = soup.select_one("#productTitle")
                if pt:
                    data["title"] = pt.get_text(strip=True)[:200]
            # 브랜드 (bylineInfo)
            if not data.get("brand"):
                byline = soup.select_one("#bylineInfo")
                if byline:
                    btext = byline.get_text(strip=True)
                    btext = btext.replace("Visit the", "").replace("Store", "").replace("브랜드:", "").strip()
                    data["brand"] = btext[:100]
            # 가격
            if not data.get("price_text"):
                price = soup.select_one(".a-price .a-offscreen") or soup.select_one(".a-price-whole")
                if price:
                    data["price_text"] = price.get_text(strip=True)[:50]

        # 3. 플랫폼별 DOM 폴백 (JSON-LD 없는 경우)
        if not data.get("images") or len(data.get("images", [])) < 2:
            existing = set(data.get("images", []))

            if platform == "iherb":
                # iHerb 상품 이미지: cloudinary /images/{brand}/{sku}/ 패턴
                import re as _re
                for img in soup.find_all("img"):
                    src = img.get("src") or img.get("data-src") or ""
                    if not src or src in existing:
                        continue
                    # 상품 갤러리 이미지 (cloudinary CDN, 상품 코드 포함)
                    if "cloudinary" in src and "/images/" in src:
                        if any(ext in src.lower() for ext in (".jpg", ".png", ".webp")):
                            # 로고/배너 제외
                            if "/brand/" not in src and "/cms/" not in src and "logo" not in src.lower():
                                existing.add(src)
                    # data-large-src (고해상도 갤러리)
                    large = img.get("data-large-src") or ""
                    if large and large not in existing and "cloudinary" in large:
                        existing.add(large)
                # iHerb 갤러리 JSON (일부 페이지에 인라인)
                html_str = str(soup)
                gallery = _re.findall(r'"(?:large|zoom)":"(https://cloudinary[^"]+)"', html_str)
                for g in gallery:
                    if g not in existing:
                        existing.add(g)
            elif platform == "amazon":
                for img in soup.find_all("img"):
                    src = img.get("data-old-hires") or img.get("src") or ""
                    if "media-amazon" in src and any(ext in src.lower() for ext in (".jpg", ".png")):
                        existing.add(src)
            elif platform in ("taobao", "tmall", "1688"):
                for img in soup.find_all("img"):
                    src = img.get("src") or img.get("data-src") or ""
                    if src.startswith("//"):
                        src = "https:" + src
                    if any(h in src for h in ("alicdn", "taobaocdn")) and any(ext in src.lower() for ext in (".jpg", ".png", ".webp")):
                        existing.add(src)
            else:
                # 일반: 큰 이미지
                for img in soup.find_all("img"):
                    src = img.get("src") or ""
                    if src.startswith("http") and any(ext in src.lower() for ext in (".jpg", ".png", ".webp")):
                        existing.add(src)
                        if len(existing) >= 10:
                            break

            data["images"] = list(existing)[:10]

        # 4. 플랫폼별 브랜드/카테고리 DOM 폴백
        if not data.get("brand"):
            if platform == "iherb":
                b = soup.select_one("#brand a") or soup.select_one(".product-brand a") or soup.select_one("[itemprop='brand']")
                if b:
                    data["brand"] = b.get_text(strip=True)[:100]
            elif platform == "amazon":
                b = soup.select_one("#bylineInfo") or soup.select_one("a#bylineInfo")
                if b:
                    data["brand"] = b.get_text(strip=True)[:100]

        if not data.get("category"):
            # Breadcrumb
            bc = soup.select(".breadcrumb a") or soup.select("nav[aria-label='breadcrumb'] a") or soup.select("#wayfinding-breadcrumbs_feature_div a")
            if bc:
                cats = [a.get_text(strip=True) for a in bc if a.get_text(strip=True)]
                if cats:
                    data["category"] = cats[-1][:50]

        # 5. 가격 DOM 폴백
        if not data.get("price_text"):
            if platform == "iherb":
                p = soup.select_one("#price") or soup.select_one(".price-inner-text") or soup.select_one("[itemprop='price']")
                if p:
                    data["price_text"] = p.get_text(strip=True)[:50]
            elif platform == "amazon":
                p = soup.select_one(".a-price .a-offscreen") or soup.select_one("#priceblock_ourprice")
                if p:
                    data["price_text"] = p.get_text(strip=True)[:50]

        # 이미지 중복 제거
        if data.get("images"):
            seen = set()
            unique = []
            for img in data["images"]:
                if img not in seen:
                    seen.add(img)
                    unique.append(img)
            data["images"] = unique[:10]

        return data

    def _extract_by_platform(self, page, platform: str) -> Dict[str, Any]:
        """플랫폼별 상품 데이터 추출 (Playwright page 객체 사용)"""
        data = {}
        try:
            if platform == "iherb":
                # iHerb는 __NEXT_DATA__ 또는 DOM에서 추출
                result = page.evaluate("""() => {
                    const getText = (sel) => document.querySelector(sel)?.textContent?.trim();
                    const getAttr = (sel, attr) => document.querySelector(sel)?.getAttribute(attr);
                    const imgs = Array.from(document.querySelectorAll('img[src*="cloudinary"], img[src*="iherb"]'))
                        .map(i => i.getAttribute('src') || i.getAttribute('data-src'))
                        .filter(s => s && /\\.(jpg|jpeg|png|webp)/i.test(s));
                    return {
                        title: getText('h1#name') || getText('h1.product-name') || getText('h1'),
                        brand: getText('#brand a') || getText('.product-brand a') || getText('[itemprop="brand"]'),
                        price: getText('#price') || getText('.price-inner-text') || getText('[itemprop="price"]') || getText('.product-price'),
                        category: getText('.breadcrumb a:last-of-type') || getText('nav[aria-label="breadcrumb"] a:last-of-type'),
                        images: [...new Set(imgs)].slice(0, 10),
                    };
                }""")
                if result:
                    data.update({k: v for k, v in result.items() if v})

            elif platform == "amazon":
                result = page.evaluate("""() => {
                    const getText = (sel) => document.querySelector(sel)?.textContent?.trim();
                    const imgs = Array.from(document.querySelectorAll('img[src*="media-amazon"], #altImages img, #imgTagWrapperId img'))
                        .map(i => (i.getAttribute('data-old-hires') || i.getAttribute('src')))
                        .filter(s => s && /\\.(jpg|jpeg|png)/i.test(s));
                    return {
                        title: getText('#productTitle') || getText('h1'),
                        brand: getText('#bylineInfo') || getText('a#bylineInfo'),
                        price: getText('.a-price .a-offscreen') || getText('#priceblock_ourprice') || getText('.a-price-whole'),
                        category: getText('#wayfinding-breadcrumbs_feature_div a:last-of-type'),
                        images: [...new Set(imgs)].slice(0, 10),
                    };
                }""")
                if result:
                    data.update({k: v for k, v in result.items() if v})

            elif platform in ("taobao", "tmall", "1688"):
                result = page.evaluate("""() => {
                    const getText = (sel) => document.querySelector(sel)?.textContent?.trim();
                    const imgs = Array.from(document.querySelectorAll('img[src*="alicdn"], img[src*="taobaocdn"]'))
                        .map(i => (i.getAttribute('src') || i.getAttribute('data-src')))
                        .filter(s => s && /\\.(jpg|jpeg|png|webp)/i.test(s))
                        .map(s => s.startsWith('//') ? 'https:' + s : s);
                    return {
                        title: getText('h1') || getText('.tb-main-title') || getText('[class*="ItemTitle"]') || getText('[class*="title"]'),
                        brand: getText('[class*="brand"]') || getText('[data-spm*="brand"]'),
                        price: getText('.tm-price') || getText('[class*="price"]') || getText('.tb-rmb-num'),
                        images: [...new Set(imgs)].slice(0, 10),
                    };
                }""")
                if result:
                    data.update({k: v for k, v in result.items() if v})

            elif platform == "rakuten":
                result = page.evaluate("""() => {
                    const getText = (sel) => document.querySelector(sel)?.textContent?.trim();
                    const imgs = Array.from(document.querySelectorAll('img[src*="rakuten.co.jp"], img[src*="r.r10s.jp"]'))
                        .map(i => i.getAttribute('src'))
                        .filter(s => s && /\\.(jpg|jpeg|png)/i.test(s));
                    return {
                        title: getText('h1') || getText('.item_name'),
                        brand: getText('.item_shopname') || getText('[class*="shop"]'),
                        price: getText('[class*="price"]') || getText('.item_current_price'),
                        images: [...new Set(imgs)].slice(0, 10),
                    };
                }""")
                if result:
                    data.update({k: v for k, v in result.items() if v})

            else:
                # 일반 사이트: 큰 이미지 + h1
                result = page.evaluate("""() => {
                    const getText = (sel) => document.querySelector(sel)?.textContent?.trim();
                    const imgs = Array.from(document.querySelectorAll('img'))
                        .filter(i => (i.naturalWidth || i.width) >= 300)
                        .map(i => i.getAttribute('src'))
                        .filter(s => s && s.startsWith('http') && /\\.(jpg|jpeg|png|webp)/i.test(s));
                    return {
                        title: getText('h1') || document.title,
                        images: [...new Set(imgs)].slice(0, 10),
                    };
                }""")
                if result:
                    data.update({k: v for k, v in result.items() if v})

            # 데이터 정리
            if data.get("title"):
                data["title"] = data["title"][:200].strip()
            if data.get("price"):
                data["price_text"] = data.pop("price")
            if data.get("brand"):
                data["brand"] = data["brand"][:100].strip()
        except Exception as e:
            self.logger.warning(f"플랫폼 파싱 실패 ({platform}): {e}")

        return data

    def _extract_fallback(self, url: str, info: Dict[str, Any]):
        """Playwright 실패 시 requests 기반 폴백"""
        try:
            import requests
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                html = resp.text
                og_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
                if og_match:
                    info["images"] = [og_match.group(1)]
                title_match = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                if title_match:
                    info["title"] = title_match.group(1).strip()[:200]
        except Exception:
            pass

    def _check_risk_keywords(self, title: str, description: str) -> tuple:
        """리스크 키워드 기반 1차 필터링"""
        risk_flags = []
        risk_details = {}

        combined_text = f"{title} {description}".lower()

        for risk_type, keywords in self.risk_keywords.items():
            matched_keywords = [kw for kw in keywords if kw.lower() in combined_text]
            if matched_keywords:
                risk_flags.append(risk_type)
                risk_details[risk_type] = matched_keywords

        return risk_flags, risk_details

    def _analyze_with_llm(self, input_model: SourcingInputSchema, risk_flags: List[str]) -> Dict[str, Any]:
        """LLM을 사용한 상세 분석"""

        if not self.client:
            # Fallback: Rule-based 간단 분석
            return {
                "product_classification": "테스트",
                "recommended_decision": "보류" if risk_flags else "통과",
                "confidence": 0.5
            }

        prompt = f"""당신은 Fortimove Global의 소싱 담당자입니다.
다음 상품 정보를 분석하여 소싱 가능 여부를 판단하십시오.

# 입력 정보
- URL: {input_model.source_url}
- 제목: {input_model.source_title or "미제공"}
- 설명: {input_model.source_description or "미제공"}
- 키워드: {', '.join(input_model.keywords) if input_model.keywords else "없음"}
- 타겟 시장: {input_model.market}

# 자동 감지된 리스크
{', '.join(risk_flags) if risk_flags else "없음"}

# 분석 기준
1. **지재권 리스크**: 유명 브랜드 모방/침해 여부
2. **통관 리스크**: 의약품, 식품 등 통관 제한 품목
3. **의료기기 리스크**: 의료적 효능 표방 여부
4. **상품 분류**: 테스트/반복/PB 중 판단

# 출력 형식 (JSON)
{{
  "product_classification": "테스트|반복|PB",
  "recommended_decision": "통과|보류|제외",
  "confidence": 0.9,
  "risk_assessment": "리스크 평가 1줄",
  "reasoning": "판단 근거 2-3줄"
}}

JSON만 반환하십시오."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = response.content[0].text.strip()

            # Markdown block cleanup
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            return json.loads(raw)

        except Exception as e:
            logger.error(f"LLM 분석 실패: {e}")
            return {
                "product_classification": "테스트",
                "recommended_decision": "보류",
                "confidence": 0.3,
                "risk_assessment": f"LLM 분석 실패: {str(e)}",
                "reasoning": "자동 분석 실패로 보류 처리"
            }

    def _generate_vendor_questions(self, input_model: SourcingInputSchema, llm_analysis: Dict) -> tuple:
        """상품별 맞춤 벤더 질문 생성 (LLM 기반 + 템플릿 폴백)"""

        title = input_model.source_title or ""
        risk_flags = llm_analysis.get("risk_flags", []) or []

        # LLM 기반 맞춤 질문 생성 시도
        try:
            from llm_router import call_llm
            prompt = f"""당신은 해외 구매대행 소싱 전문가입니다. 아래 상품을 중국 벤더(또는 해외 공급자)에게 구매하기 전에 반드시 확인해야 할 **상품별 맞춤 질문** 5개를 작성하세요.

상품명: {title}
감지된 리스크: {', '.join(risk_flags) if risk_flags else '없음'}

규칙:
- 일반적인 질문(재고/리드타임/MOQ) 외에, 이 상품의 특성에 특화된 질문을 포함
- 예: 영양제 → "성분 인증서 제공 가능?", "유통기한 6개월 이상?"
- 예: 의류 → "사이즈 스펙 시트?", "봉제 품질 보증?"
- 예: 전자제품 → "KC 인증 여부?", "A/S 정책?"
- 한국어 5개 + 중국어 5개 (같은 질문의 번역)

JSON 형식으로만 응답:
{{
  "ko": ["질문1", "질문2", "질문3", "질문4", "질문5"],
  "zh": ["问题1", "问题2", "问题3", "问题4", "问题5"]
}}"""

            raw = call_llm(task_type="copywriting", prompt=prompt, max_tokens=1000)
            import re, json as _json
            m = re.search(r'\{[\s\S]*\}', raw)
            if m:
                data = _json.loads(m.group())
                ko = data.get("ko", [])
                zh = data.get("zh", [])
                if len(ko) >= 3 and len(zh) >= 3:
                    return ko[:8], zh[:8]
        except Exception as e:
            self.logger.warning(f"맞춤 벤더 질문 생성 실패: {e}")

        # 폴백: 템플릿
        questions_ko = [
            "현재 실재고가 있나요? 품절 위험은 없나요?",
            "배송까지 걸리는 리드타임은 며칠인가요?",
            "최소 주문 수량(MOQ)이 있나요?",
            "품질 보증 및 반품 정책은 어떻게 되나요?",
        ]
        questions_zh = [
            "现在有现货吗？没有缺货风险吗？",
            "从订购到发货需要多少天？",
            "有最小订购量(MOQ)吗？",
            "质量保证和退货政策是怎样的？",
        ]

        if "지재권" in risk_flags:
            questions_ko.append("이 제품은 정품인가요? 브랜드 라이선스가 있나요?")
            questions_zh.append("这个产品是正品吗？有品牌授权吗？")
        if "통관" in risk_flags:
            questions_ko.append("한국 통관 시 필요한 서류나 인증이 있나요?")
            questions_zh.append("韩国清关时需要什么文件或认证吗？")

        return questions_ko, questions_zh

    def _make_decision(self, risk_flags: List[str], llm_analysis: Dict) -> str:
        """최종 소싱 판정"""

        # Rule 1: 치명적 리스크 (지재권, 의약품) → 제외
        # ⚠️ 2026-04-01 업데이트: 의약품 리스크 "제외" 판정으로 강화 (약사법 위반 위험)
        if "지재권" in risk_flags:
            return "제외"

        if "의약품" in risk_flags:
            return "제외"  # 약사법 위반 시 징역 10년/벌금 1억원 → 무조건 제외

        # Rule 2: 의료기기 리스크 → 제외
        # ⚠️ 2026-04-01 업데이트: 의료기기도 무조건 제외 (의료기기법 위반 위험)
        if "의료기기" in risk_flags:
            return "제외"  # 의료기기법 위반 시 징역 5년/벌금 5천만원 → 무조건 제외

        # Rule 3: LLM 추천이 제외 → 제외
        if llm_analysis.get("recommended_decision") == "제외":
            return "제외"

        # Rule 4: 2개 이상 리스크 → 보류
        if len(risk_flags) >= 2:
            return "보류"

        # Rule 5: 1개 리스크 → 보류
        if len(risk_flags) == 1:
            return "보류"

        # Rule 6: 리스크 없음 → 통과
        return "통과"

    def _recommend_next_step(self, decision: str, risk_flags: List[str]) -> str:
        """다음 단계 권고"""

        if decision == "제외":
            return "소싱 불가 - 다른 상품 검색 권장"

        elif decision == "보류":
            if "지재권" in risk_flags:
                return "변리사 검토 필요 - 상표권/디자인권 확인 후 재판단"
            elif "통관" in risk_flags:
                return "관세사 확인 필요 - 통관 가능 여부 검증 후 재판단"
            elif "의료기기" in risk_flags:
                return "상품 설명 수정 필요 - 의료적 효능 표현 제거 후 재검토"
            else:
                return "벤더에게 추가 정보 요청 후 재검토"

        else:  # 통과
            if risk_flags:
                return "주의 사항 확인 후 마진 검수 단계로 이동"
            else:
                return "마진 검수 단계로 즉시 이동 가능"

    def _check_legal_compliance(self, product_name: str, description: str, risk_flags: List[str]) -> Dict[str, Any]:
        """
        Korean Law MCP를 사용한 법령 검증

        Args:
            product_name: 상품명
            description: 상품 설명
            risk_flags: 감지된 리스크 플래그

        Returns:
            법령 검증 결과
        """
        legal_check_result = {
            "medical_device_check": None,
            "pharmaceutical_check": None,
            "recommendations": []
        }

        # 의료기기 리스크가 있는 경우
        if "의료기기" in risk_flags:
            try:
                medical_check = self.korean_law.check_medical_device_law(product_name, description)
                legal_check_result["medical_device_check"] = medical_check

                if medical_check.get("is_violation"):
                    recommendation = self.korean_law.get_law_recommendation("의료기기")
                    legal_check_result["recommendations"].append(recommendation)
                    logger.warning(f"의료기기법 위반 가능성: {medical_check.get('reason')}")
            except Exception as e:
                logger.error(f"의료기기법 검증 실패: {e}")
                legal_check_result["medical_device_check"] = {"error": str(e)}

        # 의약품 리스크가 있는 경우
        if "의약품" in risk_flags:
            try:
                pharma_check = self.korean_law.check_pharmaceutical_law(product_name, description)
                legal_check_result["pharmaceutical_check"] = pharma_check

                if pharma_check.get("is_violation"):
                    recommendation = self.korean_law.get_law_recommendation("의약품")
                    legal_check_result["recommendations"].append(recommendation)
                    logger.warning(f"약사법 위반 가능성: {pharma_check.get('reason')}")
            except Exception as e:
                logger.error(f"약사법 검증 실패: {e}")
                legal_check_result["pharmaceutical_check"] = {"error": str(e)}

        return legal_check_result
