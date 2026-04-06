"""
Competitor Monitor v2 — 실제 경쟁 셀러 분석

기능:
1. 승인된 상품 기준으로 네이버 쇼핑 경쟁 셀러 검색 링크 생성
2. 같은 카테고리 TOP 셀러 식별 (수동 + LLM 조합)
3. 경쟁 가격대 분석 (최저/평균/최고)
4. LLM으로 경쟁 강도 + 차별화 전략 생성
5. 경쟁사 약점/공략 포인트 자동 도출
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _init_competitor_tables():
    """경쟁사 분석 캐시 테이블"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS competitor_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE,
            category TEXT,
            product_name TEXT,
            data_json TEXT,
            generated_at TEXT
        )''')
        conn.commit()

_init_competitor_tables()


def _query(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


# ══════════════════════════════════════════════════════════
# 1. 우리 상품 기준 경쟁 셀러 검색 링크 생성
# ══════════════════════════════════════════════════════════

def get_our_products() -> List[Dict]:
    """우리가 다루는 상품 목록 (승인/생성된 것)"""
    rows = _query("""
        SELECT review_id, source_title, generated_naver_title, score,
               generated_price, source_data_json
        FROM approval_queue
        WHERE score >= 60
          AND (generated_naver_title IS NOT NULL OR source_title IS NOT NULL)
          AND source_title NOT LIKE '%按图片%'
          AND source_title != 'Unknown Product'
        ORDER BY score DESC
        LIMIT 20
    """)

    products = []
    for r in rows:
        title = r["generated_naver_title"] or r["source_title"] or ""
        # 카테고리 추출
        category = "supplement"
        try:
            sd = r["source_data_json"] or "{}"
            if isinstance(sd, str):
                sd = json.loads(sd)
            if isinstance(sd, dict):
                input_data = sd.get("input", {})
                category = input_data.get("category", "supplement")
        except Exception:
            pass

        # 검색 키워드 추출 (상품명에서 핵심 단어만)
        import re
        clean_title = re.sub(r'\[.*?\]', '', title).strip()  # [카테고리] 제거
        keywords = clean_title.split()[:3]  # 앞 3단어
        search_query = " ".join(keywords) if keywords else clean_title[:30]

        products.append({
            "review_id": r["review_id"],
            "title": title,
            "search_query": search_query,
            "category": category,
            "our_price": r["generated_price"] or 0,
            "score": r["score"],
        })

    return products


def generate_marketplace_search_links(product: Dict) -> Dict:
    """상품의 경쟁사 검색 링크 자동 생성"""
    query = product.get("search_query", "")
    q_enc = quote_plus(query)

    return {
        "naver_shopping": f"https://search.shopping.naver.com/search/all?query={q_enc}",
        "coupang": f"https://www.coupang.com/np/search?q={q_enc}",
        "11st": f"https://search.11st.co.kr/Search.tmall?kwd={q_enc}",
        "gmarket": f"https://browse.gmarket.co.kr/search?keyword={q_enc}",
        "auction": f"https://browse.auction.co.kr/search?keyword={q_enc}",
        "kakao_shopping": f"https://shoppinghow.kakao.com/search?q={q_enc}",
    }


# ══════════════════════════════════════════════════════════
# 2. LLM 기반 경쟁 분석 (카테고리별)
# ══════════════════════════════════════════════════════════

def analyze_competition_for_product(product: Dict, force_refresh: bool = False) -> Dict:
    """LLM으로 특정 상품의 경쟁 환경 분석"""
    cache_key = f"comp_{product.get('review_id','')}_{datetime.now().strftime('%Y-%m-%d')}"

    if not force_refresh:
        rows = _query('SELECT data_json FROM competitor_analysis WHERE cache_key=?', (cache_key,))
        if rows:
            try:
                return json.loads(rows[0]["data_json"])
            except Exception:
                pass

    title = product.get("title", "")
    our_price = product.get("our_price", 0)
    category = product.get("category", "supplement")

    prompt = f"""한국 이커머스(네이버 스마트스토어, 쿠팡, 11번가) 경쟁 분석 전문가로서,
"{title}" 상품의 한국 시장 실제 경쟁 상황을 분석하세요.

우리 판매가: ₩{our_price:,.0f}
카테고리: {category}

=== 실제 한국 시장에 있는 경쟁 셀러 유형 ===
1. 대형 유통사: 올리브영, 이마트, GS샵, 쿠팡 로켓직구
2. 전문 해외직구몰: 아이허브코리아, 와디즈, 도매꾹
3. 개인 스마트스토어 셀러 (스토어팜, 쿠팡)
4. 파워셀러 (월 1억+ 매출)
5. 구매대행 전문 셀러
6. 브랜드 공식몰 (NOW Foods, California Gold 공식)

=== 분석 요구사항 ===
실제 한국 시장을 기준으로, 이 상품을 파는 경쟁 셀러들의 특징을 분석하세요.

반드시 JSON 형식으로만 응답:
{{
  "market_heat": "시장 과열도 (낮음/보통/높음/매우 높음)",
  "competitor_count_estimate": "예상 경쟁 셀러 수 (네이버 기준)",
  "price_range": {{
    "min": 0,
    "avg": 0,
    "max": 0,
    "our_position": "저가/중가/고가 중 어디"
  }},
  "top_competitor_types": [
    {{
      "type": "셀러 유형 (예: 해외직구 파워셀러)",
      "market_share_pct": 0,
      "avg_price_krw": 0,
      "strengths": ["강점1", "강점2"],
      "weaknesses": ["약점1", "약점2"]
    }}
  ],
  "competitive_gaps": [
    "우리가 공략 가능한 경쟁사 빈틈 1",
    "우리가 공략 가능한 경쟁사 빈틈 2",
    "우리가 공략 가능한 경쟁사 빈틈 3"
  ],
  "differentiation_strategy": [
    {{"strategy": "차별화 전략", "expected_impact": "예상 효과"}}
  ],
  "price_recommendation": {{
    "suggested_price_krw": 0,
    "reasoning": "가격 추천 이유"
  }},
  "warning_flags": ["경계해야 할 경쟁 요소 1~3개"]
}}

중요: 한국 시장 현실 기반으로 작성. 추측은 "추정"으로 표시. JSON만 출력."""

    try:
        from llm_router import call_llm
        raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=2500)
        import re
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            result = json.loads(match.group())
            result["product_title"] = title
            result["our_price"] = our_price
            result["category"] = category
            result["marketplace_links"] = generate_marketplace_search_links(product)
            result["generated_at"] = datetime.now().isoformat()

            # 캐시 저장
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    conn.execute('INSERT OR REPLACE INTO competitor_analysis (cache_key, category, product_name, data_json, generated_at) VALUES (?, ?, ?, ?, ?)',
                                 (cache_key, category, title, json.dumps(result, ensure_ascii=False), datetime.now().isoformat()))
                    conn.commit()
            except Exception as e:
                logger.warning(f"경쟁사 분석 캐시 저장 실패: {e}")

            return result
    except Exception as e:
        logger.error(f"경쟁사 분석 실패: {e}")

    return {"error": True, "product_title": title}


# ══════════════════════════════════════════════════════════
# 3. 종합 경쟁 리포트 (모든 상품)
# ══════════════════════════════════════════════════════════

def get_competitor_report(force_refresh: bool = False) -> Dict[str, Any]:
    """우리 상품 전체의 경쟁 환경 종합 리포트"""
    cache_key = f"competitor_full_{datetime.now().strftime('%Y-%m-%d')}"

    if not force_refresh:
        rows = _query('SELECT data_json FROM competitor_analysis WHERE cache_key=?', (cache_key,))
        if rows:
            try:
                return json.loads(rows[0]["data_json"])
            except Exception:
                pass

    our_products = get_our_products()

    if not our_products:
        return {
            "generated_at": datetime.now().isoformat(),
            "message": "분석할 상품이 없습니다. 워크벤치에서 상품을 승인하세요.",
            "our_product_count": 0,
            "analyses": [],
            "summary": {},
        }

    # 상위 5개 상품만 상세 분석 (비용 절약)
    top_products = our_products[:5]

    analyses = []
    for p in top_products:
        analysis = analyze_competition_for_product(p, force_refresh=force_refresh)
        if not analysis.get("error"):
            analyses.append(analysis)

    # 종합 요약
    if analyses:
        overall_heat_map = {"낮음": 1, "보통": 2, "높음": 3, "매우 높음": 4}
        avg_heat = sum(overall_heat_map.get(a.get("market_heat", "보통"), 2) for a in analyses) / len(analyses)
        heat_label = "낮음" if avg_heat < 1.5 else "보통" if avg_heat < 2.5 else "높음" if avg_heat < 3.5 else "매우 높음"

        all_gaps = []
        for a in analyses:
            all_gaps.extend(a.get("competitive_gaps", []))

        warnings = []
        for a in analyses:
            warnings.extend(a.get("warning_flags", []))

        summary = {
            "analyzed_count": len(analyses),
            "overall_market_heat": heat_label,
            "top_competitive_gaps": list(set(all_gaps))[:5],
            "critical_warnings": list(set(warnings))[:3],
        }
    else:
        summary = {"analyzed_count": 0}

    result = {
        "generated_at": datetime.now().isoformat(),
        "our_product_count": len(our_products),
        "analyses": analyses,
        "summary": summary,
        # 기존 호환성
        "all_items": [],
        "industry_trends": [],
        "pricing_intelligence": [],
        "trademark_alerts": [],
    }

    # 캐시 저장
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('INSERT OR REPLACE INTO competitor_analysis (cache_key, category, product_name, data_json, generated_at) VALUES (?, ?, ?, ?, ?)',
                         (cache_key, "all", "전체", json.dumps(result, ensure_ascii=False), datetime.now().isoformat()))
            conn.commit()
    except Exception:
        pass

    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    report = get_competitor_report()
    print(f"분석된 상품: {report.get('our_product_count')}개")
    print(f"시장 과열도: {report.get('summary', {}).get('overall_market_heat', 'N/A')}")
    for a in report.get("analyses", [])[:3]:
        print(f"  - {a.get('product_title','')[:40]}")
        print(f"    경쟁자: {a.get('competitor_count_estimate','?')}, 포지션: {a.get('price_range',{}).get('our_position','?')}")
