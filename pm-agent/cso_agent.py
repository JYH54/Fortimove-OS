"""
CSO Agent v3 — Chief Strategy Officer (공격적 AI 레버리지 모드)

목표 (무조건 달성 전제):
- 단기 (2년): 매출 500억 (월 42억) — 반드시 달성
- 장기 (10년): 기업가치 2조+ 웰니스 헬스케어 대기업

핵심 가정: AI 14개 에이전트 오케스트레이션 = 팀 50명 등가 생산성
- SNS 콘텐츠 자동 생성: 일 100건 (6 플랫폼 × 16건/일)
- 소싱 자동화: 주 500개 상품 스크리닝
- 상세페이지 자동 생성: 시간당 20개
- 번역/이미지 편집 자동화: 24시간 무중단
→ 1인 법인이지만 전통 인력 기준 50명 규모 아웃풋

벤치마크 (공격적 참고):
- 닥터지(Dr.G): 5년 → 1,000억 (AI 없이)
- 스킨1004: 7년 → 기업가치 1조 (AI 없이)
- 해외직구 + AI 자동화 = 업계 최초 조합, 속도 3~5배 가능 가정

전략 원칙:
1. 무조건 500억 포트폴리오 합산 달성 (수학적 강제)
2. 웰니스/헬스케어 범주 고수 — 카테고리 미달 시 pivot 내에서만 이동
3. 법적 준수 (건기식법/약사법/표시광고법/의료기기법) 내 최대 공격성
4. AI 레버리지를 모든 가정에 반영 (SKU당 매출, 인력, 광고 효율)
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _init_cso_tables():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS cso_strategy_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_type TEXT,
            cache_key TEXT UNIQUE,
            data_json TEXT,
            generated_at TEXT
        )''')
        conn.commit()

_init_cso_tables()


def _query(sql: str, params: tuple = ()):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


class CSOAgent:
    """CSO — 2년 500억 무조건 달성 + 10년 기업가치 2조 (AI 공격 모드)"""

    # ──────────────────────────────────────────────────
    # 목표 (무조건 달성 — 수학적 강제)
    # ──────────────────────────────────────────────────
    TARGET_YEAR_2_REVENUE = 50_000_000_000   # 500억 (2년)
    TARGET_YEAR_2_MONTHLY = TARGET_YEAR_2_REVENUE / 12  # 약 42억/월

    TARGET_YEAR_10_VALUATION = 2_000_000_000_000  # 2조 (기업가치)
    TARGET_YEAR_10_REVENUE = 300_000_000_000  # 3000억 (매출 기준 역산, 멀티플 6~7x)

    # 업계 벤치마크 (LLM 프롬프트용)
    INDUSTRY_BENCHMARKS = {
        "dr_g": {"years": 5, "revenue_krw": 100_000_000_000, "model": "D2C 코스메슈티컬"},
        "skin1004": {"years": 7, "valuation_krw": 1_000_000_000_000, "model": "K뷰티 D2C"},
        "dong_kuk": {"years": 10, "revenue_krw": 300_000_000_000, "model": "웰니스 D2C"},
        "yuhan_wellness": {"years": 5, "revenue_krw": 50_000_000_000, "model": "건기식 D2C"},
        "top_cross_border": {"years": 3, "revenue_krw": 60_000_000_000, "model": "해외직구 대형 셀러"},
    }

    # ──────────────────────────────────────────────────
    # AI 레버리지 계수 (공격 모드 전제)
    # ──────────────────────────────────────────────────
    AI_LEVERAGE = {
        "equivalent_team_size": 50,          # 14 에이전트 = 인력 50명 등가
        "sku_throughput_multiplier": 10,     # SKU 관리 10배 (자동화)
        "sns_content_daily": 100,            # 일 100건 콘텐츠 (6 플랫폼)
        "marketing_efficiency_multiplier": 3, # 광고비 대비 매출 3배 (AI 타겟팅)
        "sourcing_weekly": 500,              # 주 500개 상품 스크리닝
        "speed_vs_traditional": 4,           # 전통 속도 대비 4배
    }

    # ──────────────────────────────────────────────────
    # 웰니스/헬스케어 Pivot Universe (이 범주 이탈 금지)
    # ──────────────────────────────────────────────────
    WELLNESS_PIVOT_CATEGORIES = [
        # 건기식/보충제
        "프리미엄 건기식", "프로바이오틱스", "오메가3", "비타민", "콜라겐",
        "NMN/안티에이징", "아답토젠(ashwagandha, rhodiola)",
        # 반려동물 웰니스 (법적 자유도 높음)
        "반려견 영양제", "반려견 프로바이오틱스", "반려견 덴탈케어",
        "반려견 관절/피부 보조제", "반려묘 웰니스",
        # 홈피트니스/요가
        "홈트 장비", "요가 매트/액세서리", "폼롤러/마사지건", "저항밴드",
        # 보호대/재활
        "무릎 보호대", "손목 보호대", "허리 보호대", "자세 교정",
        # 일상 웰니스
        "수면 보조 (사운드머신, 아이마스크)", "아로마테라피", "명상/호흡 기기",
        "블루라이트 차단", "자외선 차단 웨어러블",
        # 디지털 헬스 액세서리
        "스마트워치 액세서리", "혈압/혈당 모니터 액세서리", "수면 트래커",
        # 뷰티-헬스 교집합 (웰니스 뷰티)
        "LED 마스크", "두피 관리기", "갈바닉 디바이스", "더마코스메틱",
        # K-뷰티 스킨케어 (D2C 확장)
        "비건 스킨케어", "프리미엄 크림/세럼", "썬케어",
    ]

    # 법적 가드레일 (이 경계 밖으로 나가면 안 됨)
    LEGAL_GUARDRAILS = [
        "의약품 효능 주장 금지 (약사법 제61조)",
        "건기식 기능성 표시는 식약처 인정 범위만 (건강기능식품법 제14조)",
        "의료기기 등급 제품은 구매대행 가능 범위 내만 (의료기기법 제26조)",
        "소비자 오인 광고 금지 (표시광고법 제3조)",
        "질병 치료/예방 표현 절대 금지",
    ]

    def __init__(self):
        pass

    # ══════════════════════════════════════════════════════════
    # 캐시
    # ══════════════════════════════════════════════════════════

    def _get_cache(self, key: str, ttl_hours: int = 24) -> Optional[Dict]:
        try:
            rows = _query('SELECT data_json, generated_at FROM cso_strategy_cache WHERE cache_key=?', (key,))
            if rows:
                gen = datetime.fromisoformat(rows[0]["generated_at"])
                if (datetime.now() - gen).total_seconds() < ttl_hours * 3600:
                    return json.loads(rows[0]["data_json"])
        except Exception:
            pass
        return None

    def _save_cache(self, key: str, strategy_type: str, data: Dict):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO cso_strategy_cache (cache_key, strategy_type, data_json, generated_at) VALUES (?, ?, ?, ?)',
                    (key, strategy_type, json.dumps(data, ensure_ascii=False), datetime.now().isoformat())
                )
                conn.commit()
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════
    # 사업 컨텍스트
    # ══════════════════════════════════════════════════════════

    def _get_business_context(self) -> Dict:
        approved = _query("""
            SELECT source_title, score, source_data_json
            FROM approval_queue
            WHERE score >= 60 AND source_title IS NOT NULL
              AND source_title NOT LIKE '%按图片%' AND source_title != 'Unknown Product'
            ORDER BY score DESC LIMIT 30
        """)

        categories = {}
        for p in approved:
            try:
                sd = p.get("source_data_json") or "{}"
                if isinstance(sd, str):
                    sd = json.loads(sd)
                cat = sd.get("input", {}).get("category", "general")
                categories[cat] = categories.get(cat, 0) + 1
            except Exception:
                pass

        try:
            sales = _query("SELECT SUM(revenue_krw) as total, COUNT(*) as orders FROM sales_data WHERE order_date >= date('now','-30 days')")
            sales_summary = sales[0] if sales else {}
        except Exception:
            sales_summary = {}

        return {
            "approved_count": len(approved),
            "category_distribution": categories,
            "top_products": [p["source_title"][:50] for p in approved[:10]],
            "recent_sales_30d": sales_summary,
        }

    # ══════════════════════════════════════════════════════════
    # 1. 카테고리 제언 (수학 검증 내장)
    # ══════════════════════════════════════════════════════════

    def _build_aggressive_prompt(self, ctx: Dict, boost_note: str = "") -> str:
        """공격적 AI 레버리지 기반 500억 달성 프롬프트"""
        pivot_list = ", ".join(self.WELLNESS_PIVOT_CATEGORIES[:25])
        legal_list = "\n".join(f"- {g}" for g in self.LEGAL_GUARDRAILS)

        return f"""당신은 AI 네이티브 웰니스 이커머스의 CSO입니다.
Fortimove Global의 **2년 내 연매출 500억원 — 무조건 달성**이 KPI입니다.
달성 불가 주장은 CSO 해임 사유. 당신의 임무는 "어떻게 달성할 것인가"만 답하는 것.

=== 회사 정보 ===
- Fortimove Global (수원 영통, 1인 법인, 해외직구 구매대행)
- **AI 에이전트 14개 오케스트레이션** (전통 인력 50명 등가 생산성)
  · 소싱: 주 500개 상품 자동 스크리닝
  · 콘텐츠: 일 100건 SNS 자동 생성 (6 플랫폼)
  · 상세페이지: 시간당 20개 자동 생성
  · 번역/이미지 편집/리스크 분석 24시간 무중단
- 배송대행지 활용 (재고 부담 0)
- 구매대행 = 사입 없음 = 자본 효율 극대화

=== AI 레버리지 전제 (반드시 반영) ===
전통 해외직구 셀러 한계를 **무시하고** AI 자동화 효율을 전제로 계산:
- SKU 관리: 전통 대비 10배 (AI 자동 관리) → 1인이 1,000 SKU 운영 가능
- SNS 콘텐츠: 일 100건 자동 생성 → 인플루언서 대비 30배 노출
- 광고 효율 ROAS: AI 타겟팅으로 전통 대비 3배 (ROAS 5 → 15)
- 속도: 전통 4배 → 5년치 성장을 2년에 압축 가능
- 히트 상품 발굴: 주 500개 스크리닝 → 월 5~10개 히트 탄생

=== 벤치마크 (AI 없이 달성한 기록) ===
- 닥터지: 5년 → 1,000억 (전통 방식)
- 스킨1004: 7년 → 기업가치 1조 (전통 방식)
- 유한건강생활: 5년 → 500억 (전통 방식)
→ **AI 4배 속도 전제 시 2년에 500억 가능한 시장 구조 존재**

=== 웰니스/헬스케어 Pivot Universe (이 범주 내에서만 이동) ===
{pivot_list}

**중요**: 특정 카테고리 매출이 목표 미달이면 위 범주 내에서 pivot. 웰니스 이탈 금지.

=== 법적 가드레일 (절대 위반 금지, 공격은 이 안에서) ===
{legal_list}
→ 효능 주장은 구조·기능 표현만, 질병 치료 암시 금지, 식약처/KIPRIS 교차 검증.

=== 500억 달성 산수 (이 숫자를 반드시 맞출 것) ===
월 42억 = 히트 카테고리 3개 × 월 10억 + 서브 카테고리 3개 × 월 4억
또는: 히트 SKU 20개 × 월 1.5억 + 일반 SKU 500개 × 월 2,400만
ROAS 15 전제 시 광고비 월 2.8억으로 매출 42억 가능

=== 현재 보유 자산 ===
승인 상품: {ctx['approved_count']}개
카테고리 분포: {json.dumps(ctx['category_distribution'], ensure_ascii=False)}

{boost_note}

=== 출력 요구사항 ===
1. **포트폴리오 합계 = 월 4,166,666,666원 (연 500억) — 반드시 일치**
2. 3~6개 카테고리 구성 (집중 + 분산 균형)
3. 모든 카테고리는 WELLNESS_PIVOT_CATEGORIES 내에서만
4. feasibility_assessment 는 "높음" 또는 "매우 높음"만 허용 (AI 레버리지 전제)
5. 각 카테고리마다 AI 활용 방법 명시 (ai_leverage_strategy 필드)

JSON 응답:
{{
  "executive_summary": "AI 레버리지로 2년 500억을 어떻게 달성할지 3~4줄 공격적 요약",

  "reality_check": {{
    "target_monthly_krw": 4166666666,
    "required_hit_products": "히트 SKU 20개 (월 1.5억+)",
    "required_sku_count": "총 500+ SKU (AI 자동 관리)",
    "required_marketing_budget_monthly_krw": 280000000,
    "required_team_size": "1인 + AI 에이전트 14개 (= 50명 등가)",
    "feasibility_assessment": "높음 — AI 레버리지 4배 속도로 달성 가능",
    "ai_leverage_factor": "SKU 10x · 콘텐츠 30x · ROAS 3x · 속도 4x"
  }},

  "recommended_portfolio": [
    {{
      "priority": "S/A/B",
      "category": "WELLNESS_PIVOT_CATEGORIES 중 하나",
      "rationale": "한국 시장 근거 2문장 + AI 레버리지 근거 1문장",
      "target_skus": 0,
      "expected_margin_rate": 0.35,
      "category_monthly_revenue_krw": 0,
      "ai_leverage_strategy": "이 카테고리에서 AI를 어떻게 쓸 것인가 (구체)",
      "hit_product_strategy": "히트 상품 만드는 공격 전술",
      "year2_category_target_krw": 0,
      "pivot_plan": "이 카테고리 미달 시 WELLNESS_PIVOT 내 어디로 옮길지",
      "legal_compliance_note": "이 카테고리 법적 주의사항 (한 줄)",
      "similar_korean_success": "유사 성공 사례 (브랜드명 + 매출)"
    }}
  ],

  "portfolio_math_check": {{
    "sum_of_monthly_revenue_krw": 0,
    "sum_of_annual_revenue_krw": 50000000000,
    "matches_year2_target": true,
    "note": "반드시 500억(50,000,000,000)과 일치"
  }},

  "stage_targets": {{
    "month_3": {{"revenue_krw": 500000000, "skus": 50, "key_action": "AI 콘텐츠 엔진 가동 + 히트 SKU 5개 발굴"}},
    "month_6": {{"revenue_krw": 2000000000, "skus": 150, "key_action": ""}},
    "month_12": {{"revenue_krw": 8000000000, "skus": 300, "key_action": ""}},
    "month_18": {{"revenue_krw": 20000000000, "skus": 500, "key_action": ""}},
    "month_24": {{"revenue_krw": 50000000000, "skus": 700, "key_action": "500억 달성 — 시리즈 A 투자 유치"}}
  }},

  "critical_success_factors": [
    "AI 에이전트 14개 무중단 운영 (SNS, 소싱, 콘텐츠)",
    "히트 SKU 20개 확보 (월 1.5억/개)",
    "ROAS 15 이상 유지 (AI 타겟팅)"
  ],

  "key_risks": [
    {{"risk": "플랫폼 AI 콘텐츠 제재", "mitigation": "휴먼 검수 파이프라인"}},
    {{"risk": "법적 컴플라이언스", "mitigation": "표현 자동 필터 + 변호사 월 자문"}}
  ],

  "wellness_universe_locked": true,
  "legal_guardrails_respected": true,

  "resource_requirements": {{
    "year_1_capital_krw": 500000000,
    "year_1_team": "1인 + AI 14개 + 파트타임 디자이너 1명",
    "year_2_capital_krw": 3000000000,
    "year_2_team": "1인 + AI 14개 + 풀타임 3명 (CS, 디자인, 성과마케팅)"
  }}
}}

중요: 달성 불가 주장 금지. "어떻게 공격적으로 달성할지"만 답하라. JSON만 출력."""

    def recommend_categories(self, force_refresh: bool = False) -> Dict:
        cache_key = f"cso_cat_v3_{datetime.now().strftime('%Y-%m-%d')}"
        if not force_refresh:
            cached = self._get_cache(cache_key, ttl_hours=24)
            if cached:
                return cached

        ctx = self._get_business_context()

        try:
            from llm_router import call_llm
            import re

            result = None
            boost_note = ""
            max_attempts = 3

            for attempt in range(max_attempts):
                prompt = self._build_aggressive_prompt(ctx, boost_note=boost_note)
                raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=5000)
                match = re.search(r'\{[\s\S]*\}', raw)
                if not match:
                    continue
                try:
                    candidate = json.loads(match.group())
                except Exception:
                    continue

                portfolio = candidate.get("recommended_portfolio", [])
                monthly_sum = sum(p.get("category_monthly_revenue_krw", 0) for p in portfolio)
                annual_sum = monthly_sum * 12

                # 80% 이상이면 채택
                if annual_sum >= self.TARGET_YEAR_2_REVENUE * 0.8:
                    result = candidate
                    break

                # 미달 시 boost note로 재시도
                gap_억 = (self.TARGET_YEAR_2_REVENUE - annual_sum) / 100_000_000
                boost_note = (
                    f"=== 재작성 지시 (시도 {attempt+1}) ===\n"
                    f"이전 포트폴리오 합계가 연 {annual_sum/100_000_000:.0f}억 (목표 대비 {gap_억:.0f}억 부족).\n"
                    f"**반드시 연 500억에 맞춰 카테고리 매출 상향 재산출하라.**\n"
                    f"AI 레버리지 전제: SKU 10배, ROAS 3배, 광고 효율 3배. 공격적으로 계산.\n"
                    f"카테고리가 부족하면 WELLNESS_PIVOT_CATEGORIES에서 추가.\n"
                )
                result = candidate  # 마지막 후보 유지

            if result is None:
                return {"error": "JSON 파싱 실패", "message": "LLM 응답 파싱 불가"}

            # LLM 숫자 오타 방지: 상수로 강제 덮어쓰기
            if isinstance(result.get("reality_check"), dict):
                result["reality_check"]["target_monthly_krw"] = int(self.TARGET_YEAR_2_MONTHLY)
                result["reality_check"]["target_annual_krw"] = self.TARGET_YEAR_2_REVENUE

            # 수학 검증 자동 실행
            portfolio = result.get("recommended_portfolio", [])
            actual_sum_monthly = sum(p.get("category_monthly_revenue_krw", 0) for p in portfolio)
            actual_sum_annual = actual_sum_monthly * 12

            result["math_verification"] = {
                "actual_monthly_sum_krw": actual_sum_monthly,
                "actual_annual_sum_krw": actual_sum_annual,
                "target_annual_krw": self.TARGET_YEAR_2_REVENUE,
                "gap_from_target": self.TARGET_YEAR_2_REVENUE - actual_sum_annual,
                "achievement_rate_pct": round(actual_sum_annual / self.TARGET_YEAR_2_REVENUE * 100, 1),
                "verdict": "달성 가능" if actual_sum_annual >= self.TARGET_YEAR_2_REVENUE * 0.8 else "부스트 필요",
                "retry_attempts": attempt + 1,
            }

            # 웰니스 범주 검증 (키워드 기반)
            wellness_keywords = {
                "건기식", "프로바이오틱스", "오메가", "비타민", "콜라겐", "nmn", "안티에이징",
                "아답토젠", "반려", "펫", "강아지", "고양이", "덴탈", "홈트", "요가", "폼롤러",
                "마사지건", "저항밴드", "보호대", "교정", "수면", "아로마", "명상", "블루라이트",
                "스마트워치", "혈압", "혈당", "트래커", "led", "두피", "갈바닉", "더마",
                "비건", "스킨케어", "크림", "세럼", "썬케어", "웰니스", "헬스", "관절",
                "근육", "면역", "영양", "보충제", "피트니스", "재활",
            }
            def _is_wellness(cat: str) -> bool:
                c = (cat or "").lower()
                return any(k in c for k in wellness_keywords)
            in_wellness = all(_is_wellness(p.get("category", "")) for p in portfolio) if portfolio else True
            result["wellness_universe_locked"] = True
            result["wellness_compliance_check"] = in_wellness
            result["wellness_violations"] = [
                p.get("category") for p in portfolio if not _is_wellness(p.get("category", ""))
            ]

            result["ai_leverage_assumptions"] = self.AI_LEVERAGE
            result["legal_guardrails"] = self.LEGAL_GUARDRAILS
            result["generated_at"] = datetime.now().isoformat()
            result["based_on"] = ctx

            self._save_cache(cache_key, "category_v3", result)
            return result
        except Exception as e:
            logger.error(f"카테고리 제언 실패: {e}", exc_info=True)
            return {"error": True, "message": str(e)}

    # ══════════════════════════════════════════════════════════
    # 2. 10년 로드맵 — 기업가치 2조 비전
    # ══════════════════════════════════════════════════════════

    def generate_10year_vision(self, force_refresh: bool = False) -> Dict:
        cache_key = f"cso_10yr_{datetime.now().strftime('%Y-%m-%d')}"
        if not force_refresh:
            cached = self._get_cache(cache_key, ttl_hours=72)
            if cached:
                return cached

        prompt = """Fortimove Global의 **10년 내 기업가치 2조원 웰니스 헬스케어 대기업** 달성 로드맵을 수립하세요.
당신은 AI 네이티브 전략가로, "무조건 달성"이 전제. 공격적 실행 전술만 제시하라.

=== 목표 (반드시 달성) ===
- 10년 후 기업가치: ₩2조원 이상
- 달성 모델: AI 자동화 D2C → 자체 PB → K-웰니스 글로벌화 → IPO/M&A

=== AI 레버리지 전제 (모든 단계에 반영) ===
- AI 에이전트 14개 = 전통 인력 50명 등가 (팀 확장 속도 무관)
- 자동화된 소싱/콘텐츠/마케팅으로 전통 속도 대비 4배
- 즉, **닥터지 5년 → Fortimove 2년**, 스킨1004 7년 → 3년 압축 가능
- 웰니스 범주 내에서만 확장 (범주 이탈 금지)

=== 한국 웰니스 기업 벤치마크 (AI 없이 달성) ===
- 닥터지(고운세상코스메틱): 창업 18년 → 연 3,000억, 기업가치 1조+
- 스킨1004: 창업 7년 → 기업가치 1조
- 동국제약 센텔리안: 창업 10년 → 연 3,000억
- 유한건강생활: 연 500~800억
→ **AI 레버리지 전제 시 10년에 2조 달성은 공격적이지만 가능한 목표**

기업가치 2조 달성 경로 (공격 루트):
1. 매출 3,000~5,000억 + 멀티플 6~7x (웰니스 업종 평균)
2. K-웰니스 글로벌 브랜드 + 프리미엄 멀티플 10x (스킨1004 모델)
3. M&A 인수 대상 (CJ/올리브영/아모레퍼시픽/글로벌 PE)
4. Pre-IPO 라운드 밸류에이션 2조+

=== 5단계 로드맵 요구사항 ===
JSON 응답:
{
  "vision_statement": "10년 후 Fortimove Global 모습 (한 문장)",

  "stage_1_years_1_2": {
    "name": "검증기 (Validation)",
    "target_annual_revenue_krw": 50000000000,
    "target_valuation_krw": 0,
    "key_model": "해외직구 구매대행 중심",
    "team_size": 0,
    "capital_needed_krw": 0,
    "key_milestones": ["3~5개"],
    "required_pivots": "필요 전환"
  },

  "stage_2_years_3_4": {
    "name": "확장기 (Scale-up)",
    "target_annual_revenue_krw": 0,
    "target_valuation_krw": 0,
    "key_model": "히트 SKU 자체 브랜딩 + 국내 사입 시작",
    "team_size": 0,
    "capital_needed_krw": 0,
    "key_milestones": [],
    "required_pivots": ""
  },

  "stage_3_years_5_6": {
    "name": "브랜드화 (Brand Building)",
    "target_annual_revenue_krw": 0,
    "target_valuation_krw": 0,
    "key_model": "자체 PB 출시 + 인플루언서 계약 + 오프라인 진출",
    "team_size": 0,
    "capital_needed_krw": 0,
    "key_milestones": [],
    "required_pivots": ""
  },

  "stage_4_years_7_8": {
    "name": "글로벌화 (Global Expansion)",
    "target_annual_revenue_krw": 0,
    "target_valuation_krw": 0,
    "key_model": "일본/동남아 수출 + 아마존 글로벌",
    "team_size": 0,
    "capital_needed_krw": 0,
    "key_milestones": [],
    "required_pivots": ""
  },

  "stage_5_years_9_10": {
    "name": "Exit 준비 (IPO or M&A)",
    "target_annual_revenue_krw": 0,
    "target_valuation_krw": 2000000000000,
    "key_model": "IPO 상장 또는 대기업 M&A",
    "team_size": 0,
    "key_milestones": [],
    "exit_options": ["IPO (KOSDAQ)", "아모레퍼시픽 M&A", "CJ 계열 매각", "글로벌 PE 투자"]
  },

  "total_capital_required_krw": 0,
  "funding_stages": [
    {"stage": "Seed", "year": 1, "amount_krw": 0, "source": "자기자본/엔젤"},
    {"stage": "Series A", "year": 3, "amount_krw": 0, "source": "VC"},
    {"stage": "Series B", "year": 5, "amount_krw": 0, "source": "PE"}
  ],

  "biggest_risks": [
    {"risk": "리스크", "stage": "어느 단계", "mitigation": "대응"}
  ],

  "success_probability": 0,
  "aggressive_assessment": "AI 레버리지 전제 하에 어떻게 2조를 달성할지 공격적 시나리오 (불가능 주장 금지)",
  "ai_leverage_narrative": "AI 14개 에이전트가 각 단계에서 어떻게 속도를 4배로 만드는지 구체 설명"
}

중요: "불가능", "어렵다", "낮음" 표현 금지. AI 레버리지 전제로 "어떻게 달성할지"만 답하라.
JSON만 출력."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=4500)
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                self._save_cache(cache_key, "10year_vision", result)
                return result
        except Exception as e:
            logger.error(f"10년 비전 실패: {e}")

        return {"error": True}

    # ══════════════════════════════════════════════════════════
    # 3. 90일 액션 플랜
    # ══════════════════════════════════════════════════════════

    def generate_90day_roadmap(self, force_refresh: bool = False) -> Dict:
        cache_key = f"cso_90day_v2_{datetime.now().strftime('%Y-%m-%d')}"
        if not force_refresh:
            cached = self._get_cache(cache_key, ttl_hours=24)
            if cached:
                return cached

        ctx = self._get_business_context()

        prompt = f"""Fortimove Global CSO로서, **2년 내 500억 매출 달성의 첫 90일 실행 플랜**을 작성하세요.

=== 현재 상태 ===
승인 상품: {ctx['approved_count']}개
팀: 대표 1명

=== 2년 목표 ===
연 500억 = 월 42억

=== 첫 90일 현실 목표 ===
- 월 1,000만~5,000만 (학습 단계)
- 히트 상품 후보 발굴
- SNS 팔로워 기반 구축
- 운영 시스템 검증

=== 요구사항 ===
JSON 응답:
{{
  "phase_summary": "첫 90일 핵심 전략 한 문단",

  "month_1_days_1_30": {{
    "name": "MVP 검증",
    "revenue_target_krw": 10000000,
    "key_objective": "3~5개 SKU 실제 판매 시작",
    "week_1": ["구체 액션 3개"],
    "week_2": ["구체 액션 3개"],
    "week_3": ["구체 액션 3개"],
    "week_4": ["구체 액션 3개"],
    "exit_criteria": "다음 단계 진입 조건",
    "budget_krw": 0
  }},

  "month_2_days_31_60": {{
    "name": "히트 상품 탐색",
    "revenue_target_krw": 30000000,
    "key_objective": "매출 기여 TOP 3 상품 집중",
    "actions": ["6~8개"],
    "exit_criteria": "",
    "budget_krw": 0
  }},

  "month_3_days_61_90": {{
    "name": "스케일 준비",
    "revenue_target_krw": 80000000,
    "key_objective": "히트 상품 확대 + 시스템 자동화",
    "actions": [],
    "exit_criteria": "",
    "budget_krw": 0
  }},

  "daily_routines": [
    {{"time": "오전", "task": "해야 할 일"}},
    {{"time": "오후", "task": ""}},
    {{"time": "저녁", "task": ""}}
  ],

  "weekly_kpis": [
    "매주 추적할 핵심 지표 5개"
  ],

  "common_pitfalls": ["피해야 할 실수 3~5개"],

  "ai_agent_usage": {{
    "trend_intelligence": "어떻게 활용",
    "cso_agent": "어떻게 활용",
    "sns_engine": "어떻게 활용",
    "wellness_filter": "어떻게 활용"
  }}
}}

JSON만. 현실적 숫자만."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=3500)
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                self._save_cache(cache_key, "90day_v2", result)
                return result
        except Exception as e:
            logger.error(f"90일 로드맵 실패: {e}")

        return {"error": True}

    # ══════════════════════════════════════════════════════════
    # 4. 투자 우선순위
    # ══════════════════════════════════════════════════════════

    def prioritize_investments(self, monthly_budget_krw: float = 10_000_000) -> Dict:
        cache_key = f"cso_invest_v2_{int(monthly_budget_krw)}_{datetime.now().strftime('%Y-%m-%d')}"
        cached = self._get_cache(cache_key, ttl_hours=24)
        if cached:
            return cached

        prompt = f"""CSO로서, 월 예산 ₩{monthly_budget_krw:,.0f}을 2년 500억 목표를 위해 배분하세요.

=== 원칙 ===
- 초기 1~6개월: 학습과 테스트 우선 (광고 < 20%)
- 7~12개월: 히트 상품 발견 시 광고 폭주 (광고 60~70%)
- 13~24개월: 스케일 + 인력 확충

JSON:
{{
  "phase_strategy": "현재 월 예산에서 현실적 배분 전략",
  "allocation": [
    {{
      "category": "항목",
      "amount_krw": 0,
      "percentage": 0,
      "rationale": "이유",
      "expected_roas": 0,
      "priority": "P0/P1/P2",
      "kpi_to_track": "추적 지표"
    }}
  ],
  "total_krw": 0,
  "expected_monthly_revenue_generated_krw": 0,
  "expected_overall_roas": 0,
  "realistic_break_even_months": 0,
  "warnings": ["경계 사항 3개"]
}}

JSON만."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=2500)
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                result["monthly_budget_krw"] = monthly_budget_krw
                self._save_cache(cache_key, "invest_v2", result)
                return result
        except Exception as e:
            logger.error(f"투자 우선순위 실패: {e}")

        return {"error": True}

    # ══════════════════════════════════════════════════════════
    # 5. 블루오션
    # ══════════════════════════════════════════════════════════

    def find_blue_ocean(self) -> Dict:
        cache_key = f"cso_blue_v2_{datetime.now().strftime('%Y-%m-%d')}"
        cached = self._get_cache(cache_key, ttl_hours=24)
        if cached:
            return cached

        prompt = """한국 구매대행 CSO로서, 2026년 4월 기준 **경쟁 적은 블루오션 웰니스 카테고리**를 발굴하세요.

조건:
1. 한국 수요 증가 시그널 명확
2. 국내 셀러 <30개 (진입 가능)
3. 해외 인기 + 구매대행 합법
4. 객단가 5만원 이상
5. SNS 바이럴 잠재력

JSON:
{
  "blue_oceans": [
    {
      "rank": 1,
      "category": "카테고리",
      "why_blue_ocean": "근거",
      "korean_demand_signal": "시그널",
      "example_products": ["3개"],
      "estimated_margin_rate": 0,
      "estimated_monthly_revenue_per_sku_krw": 0,
      "first_mover_advantage_months": 0,
      "entry_strategy": "진입 전략",
      "similar_success_case": "유사 성공 사례"
    }
  ],
  "top_pick_rationale": "1등 이유"
}

5~7개. JSON만."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="risk_analysis", prompt=prompt, max_tokens=3000)
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result["generated_at"] = datetime.now().isoformat()
                self._save_cache(cache_key, "blue_ocean_v2", result)
                return result
        except Exception as e:
            logger.error(f"블루오션 실패: {e}")

        return {"error": True}

    # ══════════════════════════════════════════════════════════
    # 6. 전략 브리프 (홈 대시보드용)
    # ══════════════════════════════════════════════════════════

    def strategic_brief(self) -> Dict:
        categories = self.recommend_categories()
        roadmap = self.generate_90day_roadmap()
        vision = self.generate_10year_vision()

        top_portfolio = categories.get("recommended_portfolio", [])[:3]
        month_1 = roadmap.get("month_1_days_1_30", {})
        math_check = categories.get("math_verification", {})

        return {
            "headline": categories.get("executive_summary", ""),
            "reality_check": categories.get("reality_check", {}),
            "math_verification": math_check,
            "top_3_categories": [
                {
                    "priority": p.get("priority", "?"),
                    "category": p.get("category", ""),
                    "rationale": p.get("rationale", "")[:100],
                    "target_skus": p.get("target_skus", 0),
                    "category_monthly_revenue_krw": p.get("category_monthly_revenue_krw", 0),
                    "expected_margin_rate": p.get("expected_margin_rate", 0),
                    "similar_korean_success": p.get("similar_korean_success", ""),
                }
                for p in top_portfolio
            ],
            "stage_targets": categories.get("stage_targets", {}),
            "first_month_actions": month_1.get("week_1", [])[:3],
            "critical_success_factors": categories.get("critical_success_factors", [])[:3],
            "year2_target_krw": self.TARGET_YEAR_2_REVENUE,
            "year10_valuation_target_krw": self.TARGET_YEAR_10_VALUATION,
            "10year_stages": {
                "year_2": vision.get("stage_1_years_1_2", {}).get("target_annual_revenue_krw", 0),
                "year_4": vision.get("stage_2_years_3_4", {}).get("target_annual_revenue_krw", 0),
                "year_6": vision.get("stage_3_years_5_6", {}).get("target_annual_revenue_krw", 0),
                "year_8": vision.get("stage_4_years_7_8", {}).get("target_annual_revenue_krw", 0),
                "year_10_valuation": vision.get("stage_5_years_9_10", {}).get("target_valuation_krw", 0),
            },
            "generated_at": datetime.now().isoformat(),
        }
