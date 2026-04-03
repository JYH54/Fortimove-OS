"""
국가별 소싱 설정
================
소싱 국가별 환율, 관세, 물류비, 인증 요건, 플랫폼 정보를 한곳에서 관리

지원 국가: CN(중국), US(미국), JP(일본), VN(베트남)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CountryConfig:
    """국가별 소싱 설정"""
    code: str                          # CN, US, JP, VN
    name_ko: str                       # 한국어 이름
    currency: str                      # CNY, USD, JPY, VND
    exchange_rate: float               # 1통화 → KRW
    customs_tax_rate: float            # 관세율 (간이세율 기준)
    customs_threshold_usd: float       # 면세 기준 (USD)
    shipping_per_kg_krw: float         # kg당 물류비 (KRW)
    shipping_min_krw: float            # 최소 물류비
    platforms: List[Dict[str, str]]    # 주요 소싱 플랫폼
    strong_categories: List[str]       # 강점 카테고리
    required_certs: List[str]          # 필수 인증
    origin_trust_label: str            # 상세페이지 원산지 신뢰 표현
    risk_notes: List[str]              # 국가별 특이 리스크


COUNTRIES: Dict[str, CountryConfig] = {
    "CN": CountryConfig(
        code="CN",
        name_ko="중국",
        currency="CNY",
        exchange_rate=195.0,
        customs_tax_rate=0.10,
        customs_threshold_usd=100,       # 2026년 8월 개정
        shipping_per_kg_krw=5000,
        shipping_min_krw=3000,
        platforms=[
            {"name": "타오바오", "url": "taobao.com", "type": "B2C"},
            {"name": "1688", "url": "1688.com", "type": "B2B"},
            {"name": "티몰", "url": "tmall.com", "type": "B2C"},
            {"name": "핀둬둬", "url": "pinduoduo.com", "type": "B2C"},
        ],
        strong_categories=["general", "electronics", "fitness", "beauty"],
        required_certs=["KC인증(전자)", "전기용품안전확인", "어린이제품안전인증"],
        origin_trust_label="중국 직수입 | Fortimove 품질 검수 완료",
        risk_notes=[
            "지재권 침해 상품 주의 (브랜드 모방품)",
            "KC인증 필수 (전자제품, 어린이용품)",
            "2026년 8월 간이통관 면세 USD 150→100 하향",
        ],
    ),
    "US": CountryConfig(
        code="US",
        name_ko="미국",
        currency="USD",
        exchange_rate=1380.0,
        customs_tax_rate=0.08,
        customs_threshold_usd=150,
        shipping_per_kg_krw=12000,
        shipping_min_krw=8000,
        platforms=[
            {"name": "iHerb", "url": "iherb.com", "type": "건강식품"},
            {"name": "Amazon US", "url": "amazon.com", "type": "종합"},
            {"name": "Vitacost", "url": "vitacost.com", "type": "영양제"},
            {"name": "GNC", "url": "gnc.com", "type": "영양제"},
        ],
        strong_categories=["supplement", "wellness", "fitness", "healthcare"],
        required_certs=["식약처 수입신고(건강기능식품)", "영양성분표시"],
        origin_trust_label="미국 직수입 | FDA 등록 시설 생산",
        risk_notes=[
            "건강기능식품 수입 시 식약처 사전신고 필수",
            "FDA 등록 여부 확인 (GMP 인증)",
            "관세 면세 기준 USD 150 (2026년 현행)",
            "미국산 프리미엄 이미지로 높은 마진 가능",
        ],
    ),
    "JP": CountryConfig(
        code="JP",
        name_ko="일본",
        currency="JPY",
        exchange_rate=9.2,               # 1엔 ≈ 9.2원
        customs_tax_rate=0.08,
        customs_threshold_usd=150,
        shipping_per_kg_krw=8000,
        shipping_min_krw=5000,
        platforms=[
            {"name": "라쿠텐", "url": "rakuten.co.jp", "type": "종합"},
            {"name": "Amazon JP", "url": "amazon.co.jp", "type": "종합"},
            {"name": "Qoo10 JP", "url": "qoo10.jp", "type": "종합"},
            {"name": "코스메", "url": "cosme.net", "type": "뷰티"},
        ],
        strong_categories=["beauty", "wellness", "food", "supplement"],
        required_certs=["화장품수입신고(화장품)", "식약처 수입신고(식품)"],
        origin_trust_label="일본 직수입 | 일본 후생노동성 기준 생산",
        risk_notes=[
            "일본 화장품: 한국 화장품법 기준 성분 확인 필수",
            "식품: 방사능 검사 증명서 요구 가능",
            "일본산 프리미엄 이미지 (특히 뷰티/스킨케어)",
            "엔저 시기 마진 유리 — 환율 모니터링 중요",
        ],
    ),
    "VN": CountryConfig(
        code="VN",
        name_ko="베트남",
        currency="VND",
        exchange_rate=0.056,             # 1동 ≈ 0.056원
        customs_tax_rate=0.10,
        customs_threshold_usd=100,
        shipping_per_kg_krw=6000,
        shipping_min_krw=4000,
        platforms=[
            {"name": "Shopee VN", "url": "shopee.vn", "type": "종합"},
            {"name": "Lazada VN", "url": "lazada.vn", "type": "종합"},
            {"name": "현지 공장 직거래", "url": "", "type": "B2B"},
        ],
        strong_categories=["food", "general", "beauty"],
        required_certs=["식품수입신고", "검역증명"],
        origin_trust_label="베트남 직수입 | 현지 품질 검수 완료",
        risk_notes=[
            "식품/농산물 가격 경쟁력 우수",
            "품질 편차 큼 — 샘플 검수 필수",
            "검역/위생 증명 요구 (식품류)",
            "물류 리드타임 길 수 있음 (7~14일)",
        ],
    ),
}


def get_country(code: str) -> Optional[CountryConfig]:
    """국가 코드로 설정 조회 (CN/US/JP/VN)"""
    return COUNTRIES.get(code.upper())


def detect_country_from_url(url: str) -> str:
    """URL에서 소싱 국가 자동 감지"""
    url_lower = url.lower()

    # 중국
    if any(d in url_lower for d in ["taobao.com", "1688.com", "tmall.com", "pinduoduo.com", "jd.com"]):
        return "CN"
    # 미국
    if any(d in url_lower for d in ["iherb.com", "amazon.com", "vitacost.com", "gnc.com"]):
        return "US"
    # 일본
    if any(d in url_lower for d in ["rakuten.co.jp", "amazon.co.jp", "qoo10.jp", "cosme.net"]):
        return "JP"
    # 베트남
    if any(d in url_lower for d in ["shopee.vn", "lazada.vn"]):
        return "VN"

    return "CN"  # 기본값


def detect_country_from_currency(price_str: str) -> str:
    """가격 문자열에서 통화 감지"""
    price_str = str(price_str).strip()
    if price_str.startswith("$") or "usd" in price_str.lower():
        return "US"
    if price_str.startswith("¥") or "円" in price_str:
        # 엔 vs 위안 구분 (금액 크기로)
        import re
        nums = re.findall(r'[\d.]+', price_str)
        if nums and float(nums[0]) > 500:
            return "JP"  # 엔은 보통 500 이상
        return "CN"
    if "₫" in price_str or "vnd" in price_str.lower():
        return "VN"
    return "CN"


def get_all_platforms() -> List[Dict]:
    """전체 지원 플랫폼 목록"""
    result = []
    for code, config in COUNTRIES.items():
        for p in config.platforms:
            result.append({
                "country": code,
                "country_ko": config.name_ko,
                **p
            })
    return result


def print_country_guide(code: str):
    """국가별 소싱 가이드 출력"""
    c = get_country(code)
    if not c:
        print(f"❌ 지원하지 않는 국가: {code}")
        return

    print(f"\n{'='*50}")
    print(f"  {c.name_ko} ({c.code}) 소싱 가이드")
    print(f"{'='*50}")
    print(f"  통화: {c.currency} (1{c.currency} = ₩{c.exchange_rate:,.1f})")
    print(f"  관세율: {c.customs_tax_rate*100:.0f}%")
    print(f"  면세기준: USD {c.customs_threshold_usd}")
    print(f"  물류비: ₩{c.shipping_per_kg_krw:,}/kg (최소 ₩{c.shipping_min_krw:,})")
    print()

    print(f"  강점 카테고리: {', '.join(c.strong_categories)}")
    print(f"  필수 인증: {', '.join(c.required_certs)}")
    print(f"  상세페이지 표기: \"{c.origin_trust_label}\"")
    print()

    print(f"  주요 플랫폼:")
    for p in c.platforms:
        print(f"    • {p['name']} ({p['type']}) — {p.get('url', '직거래')}")
    print()

    print(f"  리스크/주의사항:")
    for note in c.risk_notes:
        print(f"    ⚠️  {note}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print_country_guide(sys.argv[1])
    else:
        for code in COUNTRIES:
            print_country_guide(code)
            print()
