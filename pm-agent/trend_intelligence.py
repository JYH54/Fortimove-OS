"""
Trend Intelligence Agent — 매크로 시장 트렌드 분석 에이전트

역할:
- Daily Scout가 수집한 상품들을 메타 분석
- LLM으로 매크로 트렌드 발견 (Brainergy, GLP-1, Longevity 같은 축)
- 고마진 상품 자동 발굴 (순이익 70%+)
- 성장 카테고리/키워드 추출
- 구체적 액션 제안

비용:
- Gemini Flash 2.5 하루 1회 호출 (~2500 토큰)
- 월 예상 비용: ₩100 이하
- 캐싱으로 API 절약
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")
CACHE_FILE = Path(__file__).parent / "data" / "trend_intelligence_cache.json"


class TrendIntelligenceAgent:
    """매크로 트렌드 분석 및 고마진 상품 발굴"""

    def __init__(self):
        self._init_cache_table()

    def _init_cache_table(self):
        """트렌드 캐시 테이블 생성"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS trend_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE,
                data_json TEXT,
                generated_at TEXT,
                expires_at TEXT
            )''')
            conn.commit()

    def _get_cached(self, cache_key: str, ttl_hours: int = 12) -> Optional[Dict]:
        """캐시 조회 — ttl_hours 시간 이내 데이터면 반환"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    'SELECT data_json, generated_at FROM trend_cache WHERE cache_key=?',
                    (cache_key,)
                ).fetchone()
                if not row:
                    return None
                generated = datetime.fromisoformat(row['generated_at'])
                if (datetime.now() - generated).total_seconds() < ttl_hours * 3600:
                    return json.loads(row['data_json'])
        except Exception as e:
            logger.warning(f"캐시 조회 실패: {e}")
        return None

    def _save_cache(self, cache_key: str, data: Dict):
        """캐시 저장"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                now = datetime.now().isoformat()
                expires = (datetime.now() + timedelta(hours=24)).isoformat()
                conn.execute(
                    'INSERT OR REPLACE INTO trend_cache (cache_key, data_json, generated_at, expires_at) VALUES (?, ?, ?, ?)',
                    (cache_key, json.dumps(data, ensure_ascii=False), now, expires)
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"캐시 저장 실패: {e}")

    def _fetch_scout_products(self, limit: int = 50) -> List[Dict]:
        """Daily Scout에서 최근 상품 목록 가져오기 (서버 꺼져있으면 approval_queue에서 폴백)"""
        try:
            import httpx
            resp = httpx.get(f"http://localhost:8050/api/products?limit={limit}", timeout=3)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if items:
                    return items
        except Exception as e:
            logger.info(f"Daily Scout 연결 실패 → approval_queue 폴백: {e}")

        # 폴백: approval_queue에서 상품 정보 가져오기
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('''
                    SELECT source_title, score, source_data_json
                    FROM approval_queue
                    WHERE source_title IS NOT NULL
                    ORDER BY created_at DESC LIMIT ?
                ''', (limit,)).fetchall()
                fallback_items = []
                for r in rows:
                    fallback_items.append({
                        "product_name": r["source_title"],
                        "trend_score": r["score"] or 0,
                        "region": "us",
                        "category": "웰니스",
                        "korea_demand": "보통",
                    })
                return fallback_items
        except Exception as e:
            logger.warning(f"폴백도 실패: {e}")
            return []

    def _fetch_approval_queue(self, limit: int = 30) -> List[Dict]:
        """승인 큐에서 스코어 높은 상품 가져오기 (실제 분석된 상품)"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('''
                    SELECT source_title, score, decision, generated_naver_title, raw_agent_output
                    FROM approval_queue
                    WHERE score > 0
                    ORDER BY score DESC, created_at DESC
                    LIMIT ?
                ''', (limit,)).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"큐 조회 실패: {e}")
            return []

    # ══════════════════════════════════════════════════════════
    # 1. 매크로 트렌드 분석 (일 1회 실행, 12시간 캐싱)
    # ══════════════════════════════════════════════════════════

    def analyze_macro_trends(self, force_refresh: bool = False) -> Dict:
        """매크로 시장 트렌드 분석 — Brainergy, GLP-1, Longevity 같은 축 발견"""
        cache_key = f"macro_trends_{datetime.now().strftime('%Y-%m-%d')}"

        if not force_refresh:
            cached = self._get_cached(cache_key, ttl_hours=12)
            if cached:
                logger.info("매크로 트렌드 캐시 HIT")
                return cached

        # 데이터 수집
        scout_products = self._fetch_scout_products(limit=50)
        analyzed = self._fetch_approval_queue(limit=30)

        # 상품명 + 카테고리 + 트렌드 점수 요약
        product_summary = []
        for p in scout_products[:30]:
            name = p.get("product_name", "")[:60]
            cat = p.get("category", "")
            trend = p.get("trend_score", 0)
            region = p.get("region", "")
            demand = p.get("korea_demand", "")
            product_summary.append(f"- [{region}] {name} | {cat} | 트렌드{trend} | 한국수요:{demand}")

        for p in analyzed[:15]:
            name = (p.get("source_title") or "")[:60]
            score = p.get("score", 0)
            product_summary.append(f"- [분석완료] {name} | 스코어{score}")

        products_text = "\n".join(product_summary[:40])

        prompt = f"""당신은 한국 크로스보더 이커머스 시장 분석 전문가입니다.
현재 발굴된 글로벌 웰니스/헬스케어 상품 목록을 분석하여 매크로 트렌드를 도출하세요.

=== 현재 수집된 상품 목록 ===
{products_text}

=== 2026년 4월 기준 반드시 고려할 글로벌 트렌드 ===
- Brainergy (뇌 활력): 사자갈기버섯, 크레아틴 츄어블, 누트로픽
- GLP-1 컴패니언 (비만약 동반): 베르베린, 아커만시아, 전해질
- Longevity (항노화): NMN, 레스베라트롤, 스페르미딘
- Organ Meat (전통 재발견): 비프 리버, Nose-to-Tail 영양
- 여성 웰니스: 미오이노시톨, 완경 서포트
- 포스트바이오틱스: 4세대 유산균

=== 요구 사항 ===
한국 시장에서 돌풍을 일으킬 "매출 100억 목표"를 위한 분석을 제공하세요.

반드시 아래 JSON 형식으로만 응답:
{{
  "macro_axes": [
    {{
      "name": "축 이름 (예: Brainergy)",
      "korean_name": "한국어 설명",
      "description": "이 축이 왜 뜨는가 (2~3문장)",
      "growth_rate": "예상 성장률 (%)",
      "target_customer": "주요 타겟 고객",
      "key_products": ["대표 상품 3~5개"],
      "korean_market_fit": "한국 시장 적합도 (높음/보통/낮음)",
      "action_priority": "P0/P1/P2"
    }}
  ],
  "hot_keywords": [
    {{"keyword": "키워드", "reason": "왜 뜨는지", "search_volume_trend": "검색량 추이"}}
  ],
  "emerging_categories": ["신흥 카테고리 5개"],
  "declining_categories": ["쇠퇴 카테고리 3개"],
  "korean_specific_opportunities": [
    {{"opportunity": "기회", "reason": "이유", "estimated_margin": "예상 마진율"}}
  ],
  "top_3_recommendations": [
    {{
      "priority": 1,
      "category": "카테고리",
      "specific_products": ["구체 상품 2~3개"],
      "why_now": "왜 지금인가",
      "expected_margin_rate": 0,
      "expected_monthly_revenue_krw": 0,
      "risk_level": "낮음/보통/높음"
    }}
  ],
  "summary": "CEO를 위한 한줄 요약"
}}

중요: JSON만 출력, 설명 불필요."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=3500)

            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                result["data_sources"] = {
                    "scout_products": len(scout_products),
                    "analyzed_products": len(analyzed),
                }
                self._save_cache(cache_key, result)
                logger.info(f"매크로 트렌드 분석 완료: {len(result.get('macro_axes',[]))} axes")
                return result
        except Exception as e:
            logger.error(f"매크로 트렌드 분석 실패: {e}")

        # 폴백: 캐시된 기본값
        return {
            "macro_axes": [],
            "hot_keywords": [],
            "summary": "분석 실패 — 나중에 다시 시도",
            "error": True,
        }

    # ══════════════════════════════════════════════════════════
    # 2. 고마진 상품 발굴
    # ══════════════════════════════════════════════════════════

    def find_high_margin_opportunities(self, force_refresh: bool = False) -> Dict:
        """순이익 70%+ 고마진 상품 자동 발굴"""
        cache_key = f"high_margin_{datetime.now().strftime('%Y-%m-%d')}"

        if not force_refresh:
            cached = self._get_cached(cache_key, ttl_hours=12)
            if cached:
                return cached

        scout_products = self._fetch_scout_products(limit=50)

        product_list = []
        for p in scout_products[:30]:
            name = p.get("product_name", "")[:70]
            price = p.get("price", "")
            region = p.get("region", "")
            trend = p.get("trend_score", 0)
            product_list.append(f"- [{region}] {name} | {price} | 트렌드{trend}")

        prompt = f"""당신은 한국 크로스보더 이커머스 마진 분석 전문가입니다.
아래 상품 목록에서 **순이익률 70% 이상** 가능한 고마진 기회를 찾아주세요.

=== 상품 목록 ===
{chr(10).join(product_list[:30])}

=== 마진율 계산 공식 ===
한국 판매가 = 원가 × 3.5배 (해외 구매대행 일반적)
실제 마진율 = (판매가 - 원가 - 관세 - 배송 - 플랫폼수수료) / 판매가

=== 고마진 상품의 특징 ===
1. 원가 $10~$30 (소형, 가벼움)
2. 한국 판매가 ₩50,000~₩150,000 설정 가능
3. 프리미엄 브랜드 or 희소성
4. 구독 모델 가능 (재구매율 높음)
5. NMN, 사자갈기버섯, 크레아틴 구미, 베르베린 같은 카테고리

JSON으로 응답:
{{
  "high_margin_products": [
    {{
      "rank": 1,
      "product_name": "상품명",
      "estimated_source_price_usd": 0,
      "recommended_korean_price_krw": 0,
      "estimated_margin_rate": 0,
      "estimated_monthly_profit_krw": 0,
      "category": "카테고리",
      "why_high_margin": "왜 고마진인가 (1~2문장)",
      "subscription_potential": "구독 모델 가능성 (높음/보통/낮음)",
      "recommended_source_url_pattern": "iHerb/Amazon/1688 등 추천 소싱처"
    }}
  ],
  "total_opportunity_krw": 0,
  "top_pick": "가장 추천하는 1개 이유"
}}

상위 5~8개만 JSON으로. 다른 설명 금지."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=2500)

            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                self._save_cache(cache_key, result)
                return result
        except Exception as e:
            logger.error(f"고마진 분석 실패: {e}")

        return {"high_margin_products": [], "error": True}

    # ══════════════════════════════════════════════════════════
    # 3. 일일 인사이트 (홈 대시보드용, 짧고 강렬한 한줄)
    # ══════════════════════════════════════════════════════════

    def daily_brief(self) -> Dict:
        """오늘의 트렌드 브리프 — 한 줄 핵심 + 액션 3개"""
        cache_key = f"daily_brief_{datetime.now().strftime('%Y-%m-%d')}"
        cached = self._get_cached(cache_key, ttl_hours=6)
        if cached:
            return cached

        # 매크로 트렌드에서 가져오기 (이미 캐시됨)
        macro = self.analyze_macro_trends()
        high_margin = self.find_high_margin_opportunities()

        top_axes = macro.get("macro_axes", [])[:3]
        top_products = high_margin.get("high_margin_products", [])[:3]

        brief = {
            "headline": macro.get("summary", ""),
            "top_axes": [
                {
                    "name": a.get("name", ""),
                    "korean": a.get("korean_name", ""),
                    "growth": a.get("growth_rate", ""),
                    "priority": a.get("action_priority", "P2"),
                }
                for a in top_axes
            ],
            "top_high_margin": [
                {
                    "product": p.get("product_name", ""),
                    "margin_rate": p.get("estimated_margin_rate", 0),
                    "monthly_profit": p.get("estimated_monthly_profit_krw", 0),
                }
                for p in top_products
            ],
            "total_opportunity_krw": high_margin.get("total_opportunity_krw", 0),
            "generated_at": datetime.now().isoformat(),
        }

        self._save_cache(cache_key, brief)
        return brief
