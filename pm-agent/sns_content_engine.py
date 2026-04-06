"""
SNS Content Engine — 5000억 매출의 핵심 바이럴 엔진

기능:
1. 플랫폼별 최적화 콘텐츠 자동 생성 (인스타/블로그/스레드/유튜브숏츠/틱톡)
2. 자동 포스팅 스케줄 (14~90일 캘린더)
3. 인플루언서 매칭 (카테고리별 접촉 리스트)
4. 바이럴 후킹 구조 (훅→질문→대조→증거→CTA)
5. 리타겟팅 (장바구니 이탈/재구매)
6. A/B 테스트 카피 변형
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


def _init_sns_tables():
    """SNS 콘텐츠 관리 테이블"""
    with sqlite3.connect(DB_PATH) as conn:
        # 생성된 콘텐츠 저장
        conn.execute('''CREATE TABLE IF NOT EXISTS sns_contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            review_id TEXT,
            product_name TEXT,
            platform TEXT,
            content_type TEXT,
            tone TEXT,
            hook TEXT,
            body TEXT,
            cta TEXT,
            hashtags TEXT,
            full_content TEXT,
            variant TEXT DEFAULT 'A',
            scheduled_at TEXT,
            posted_at TEXT,
            status TEXT DEFAULT 'draft',
            performance_json TEXT,
            created_at TEXT
        )''')

        # 인플루언서 리스트
        conn.execute('''CREATE TABLE IF NOT EXISTS influencer_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            platform TEXT,
            handle TEXT,
            followers INTEGER DEFAULT 0,
            category TEXT,
            korea_relevance TEXT,
            avg_engagement_rate REAL DEFAULT 0,
            estimated_cost_krw REAL DEFAULT 0,
            contact_info TEXT,
            match_score REAL DEFAULT 0,
            status TEXT DEFAULT 'new',
            notes TEXT,
            created_at TEXT
        )''')

        # 콘텐츠 캘린더
        conn.execute('''CREATE TABLE IF NOT EXISTS content_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_date TEXT,
            time_slot TEXT,
            platform TEXT,
            content_id INTEGER,
            product_name TEXT,
            campaign_type TEXT,
            status TEXT DEFAULT 'planned',
            created_at TEXT
        )''')
        conn.commit()

_init_sns_tables()


# ══════════════════════════════════════════════════════════
# 1. 플랫폼별 최적화 콘텐츠 생성
# ══════════════════════════════════════════════════════════

class SNSContentEngine:
    """바이럴 SNS 콘텐츠 엔진"""

    PLATFORMS = {
        "instagram_reels": {
            "format": "릴스 (15~60초)",
            "structure": "훅 3초 → 문제 제시 7초 → 해결 20초 → 증거 15초 → CTA 5초",
            "hook_pattern": "강렬한 질문/충격적 통계/비포애프터",
            "length": "캡션 220자, 해시태그 30개",
        },
        "instagram_feed": {
            "format": "피드 포스트 (캐러셀 10장)",
            "structure": "표지 → 문제 → 이유 → 해결 → 증거 → 후기 → CTA",
            "hook_pattern": "질문형 제목 + 색상 대비 썸네일",
            "length": "캡션 500자 + 해시태그 30개",
        },
        "naver_blog": {
            "format": "블로그 포스트 (1500~3000자)",
            "structure": "도입 → 문제 → 원인 → 해결책 → 사용후기 → 결론",
            "hook_pattern": "경험담 서두 + 중간 이미지 5~8장",
            "length": "1500~3000자, 이미지 5~8장",
        },
        "youtube_shorts": {
            "format": "유튜브 숏츠 (15~60초)",
            "structure": "3초 훅 → 본론 45초 → CTA 5초",
            "hook_pattern": "이게 진짜라고요? / 충격 반응",
            "length": "제목 70자, 설명 300자",
        },
        "thread": {
            "format": "스레드 (1~5개 연속)",
            "structure": "훅 트윗 → 배경 → 핵심 → 증거 → CTA",
            "hook_pattern": "논란형 주장 / 개인 경험담",
            "length": "280자 × 5개",
        },
        "tiktok": {
            "format": "틱톡 (15~30초)",
            "structure": "임팩트 훅 → 스토리 → 반전 → CTA",
            "hook_pattern": "POV, 챌린지, 트렌드 사운드 활용",
            "length": "150자 + 트렌드 해시태그",
        },
    }

    TONES = {
        "expert": "전문가/의사 톤 — 과학적 근거 제시",
        "friend": "친구 추천 톤 — 진솔한 경험담",
        "trendy": "MZ 트렌디 톤 — 밈/유행어 활용",
        "urgent": "긴급 세일 톤 — FOMO 유발",
        "educational": "교육 톤 — 알려주는 정보 콘텐츠",
        "storytelling": "스토리텔링 톤 — 감정 이입",
    }

    def generate_platform_content(
        self,
        product_name: str,
        category: str,
        key_benefits: List[str],
        target_audience: str,
        platform: str = "instagram_reels",
        tone: str = "expert",
        variant: str = "A",
    ) -> Dict:
        """플랫폼 + 톤 조합으로 최적화 콘텐츠 생성"""
        platform_info = self.PLATFORMS.get(platform, self.PLATFORMS["instagram_reels"])
        tone_desc = self.TONES.get(tone, self.TONES["expert"])

        # 컴플라이언스 강화 프롬프트 (한국 법규 준수)
        prompt = f"""당신은 한국 SNS 바이럴 마케팅 전문가입니다.
"{product_name}" 상품의 {platform_info['format']} 콘텐츠를 만드세요.

=== 상품 정보 ===
상품: {product_name}
카테고리: {category}
주요 혜택: {', '.join(key_benefits[:5])}
타겟 고객: {target_audience}

=== 플랫폼 규격 ===
{platform_info['format']}
구조: {platform_info['structure']}
훅 패턴: {platform_info['hook_pattern']}
분량: {platform_info['length']}

=== 톤 ===
{tone_desc}

=== 변형 ===
Variant {variant} (A/B 테스트용)

=== 한국 법규 반드시 준수 ===
- 절대 금지: 치료, 완치, 질병 예방, 의학적 효과, 100% 효과, 즉시 효과
- 허용 표현: "~에 도움을 줄 수 있어요", "~을 서포트해요", "~관리에 좋아요"
- 의료기기/의약품 효능 표현 금지
- 식약처 인정 기능성 외 건강 기능 단정 금지

JSON 형식으로만 응답:
{{
  "hook": "첫 3초 스크롤 멈춤용 훅 (1~2문장)",
  "body": "본문 (플랫폼 분량에 맞춤)",
  "cta": "행동 유도 (네이버 스마트스토어 구매 유도)",
  "hashtags": ["태그1", "태그2", ...],
  "full_content": "위 3개를 합친 완성본 (바로 복붙 가능)",
  "thumbnail_text": "썸네일에 들어갈 큰 글씨 (5단어 이내)",
  "color_palette": "비주얼 톤 제안",
  "engagement_prediction": "예상 반응 (높음/보통/낮음)",
  "posting_time_recommendation": "최적 게시 시간 (한국 시간)"
}}
JSON만 출력."""

        try:
            from llm_router import call_llm
            raw = call_llm(task_type="copywriting", prompt=prompt, max_tokens=1500)

            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                result = json.loads(match.group())
                result.update({
                    "platform": platform,
                    "tone": tone,
                    "variant": variant,
                    "generated_at": datetime.now().isoformat(),
                })
                return result
        except Exception as e:
            logger.error(f"SNS 콘텐츠 생성 실패: {e}")

        return {"error": True, "platform": platform, "tone": tone}

    def generate_full_campaign(self, product_name: str, category: str, key_benefits: List[str], target_audience: str, review_id: str = None) -> Dict:
        """하나의 상품에 대해 6개 플랫폼 × 2개 톤 = 12개 콘텐츠 생성"""
        platforms = ["instagram_reels", "instagram_feed", "naver_blog", "youtube_shorts", "tiktok"]
        tones = ["expert", "friend"]

        campaign = {
            "product_name": product_name,
            "review_id": review_id,
            "generated_at": datetime.now().isoformat(),
            "contents": [],
        }

        for platform in platforms:
            for tone in tones:
                content = self.generate_platform_content(
                    product_name=product_name,
                    category=category,
                    key_benefits=key_benefits,
                    target_audience=target_audience,
                    platform=platform,
                    tone=tone,
                    variant="A",
                )
                if not content.get("error"):
                    # DB 저장
                    try:
                        with sqlite3.connect(DB_PATH) as conn:
                            conn.execute('''
                                INSERT INTO sns_contents
                                (review_id, product_name, platform, content_type, tone, hook, body, cta, hashtags, full_content, variant, status, created_at)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                review_id, product_name, platform, platform, tone,
                                content.get("hook", ""), content.get("body", ""), content.get("cta", ""),
                                json.dumps(content.get("hashtags", []), ensure_ascii=False),
                                content.get("full_content", ""), "A", "draft",
                                datetime.now().isoformat()
                            ))
                            conn.commit()
                    except Exception as e:
                        logger.warning(f"SNS DB 저장 실패: {e}")

                    campaign["contents"].append({
                        "platform": platform,
                        "tone": tone,
                        "preview": content.get("hook", "")[:80],
                    })

        return campaign


# ══════════════════════════════════════════════════════════
# 2. 자동 포스팅 캘린더 (90일 계획)
# ══════════════════════════════════════════════════════════

def generate_posting_calendar(days: int = 30, posts_per_day: int = 3) -> Dict:
    """향후 N일간 포스팅 캘린더 자동 생성"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            # 승인된 상품
            products = [dict(r) for r in conn.execute('''
                SELECT review_id, source_title, generated_naver_title, score
                FROM approval_queue
                WHERE generated_naver_title IS NOT NULL AND score >= 60
                ORDER BY score DESC LIMIT 50
            ''').fetchall()]
    except Exception:
        products = []

    if not products:
        return {"error": "승인된 상품이 없습니다", "schedule": []}

    # 최적 포스팅 시간대
    time_slots = {
        "morning": "08:00",   # 출근길
        "lunch": "12:30",     # 점심시간
        "evening": "20:00",   # 저녁
    }

    # 플랫폼 순환
    platforms = ["instagram_reels", "naver_blog", "instagram_feed", "youtube_shorts", "tiktok"]

    schedule = []
    for day in range(days):
        date = (datetime.now() + timedelta(days=day)).strftime("%Y-%m-%d")
        for slot_idx in range(posts_per_day):
            product = products[(day * posts_per_day + slot_idx) % len(products)]
            platform = platforms[(day + slot_idx) % len(platforms)]
            time_key = list(time_slots.keys())[slot_idx % len(time_slots)]

            schedule.append({
                "day": day + 1,
                "date": date,
                "time": time_slots[time_key],
                "platform": platform,
                "product_name": product.get("generated_naver_title") or product.get("source_title"),
                "review_id": product.get("review_id"),
                "campaign_type": "product_intro" if day % 3 == 0 else "benefit_focus" if day % 3 == 1 else "social_proof",
            })

    # DB 저장
    try:
        with sqlite3.connect(DB_PATH) as conn:
            for item in schedule:
                conn.execute('''
                    INSERT INTO content_calendar (schedule_date, time_slot, platform, product_name, campaign_type, status, created_at)
                    VALUES (?, ?, ?, ?, ?, 'planned', ?)
                ''', (item["date"], item["time"], item["platform"], item["product_name"], item["campaign_type"], datetime.now().isoformat()))
            conn.commit()
    except Exception as e:
        logger.warning(f"캘린더 저장 실패: {e}")

    return {
        "days": days,
        "total_posts": len(schedule),
        "products_used": len(products),
        "platforms": list(set([s["platform"] for s in schedule])),
        "schedule": schedule,
    }


# ══════════════════════════════════════════════════════════
# 3. 인플루언서 매칭 (한국 웰니스 크리에이터)
# ══════════════════════════════════════════════════════════

KOREAN_WELLNESS_INFLUENCERS = [
    # 실제 접촉 가능한 예시 (대표님이 직접 업데이트할 시드 데이터)
    {"name": "웰니스 리뷰어", "platform": "instagram", "category": "비타민", "followers_range": "10k-50k", "tier": "마이크로"},
    {"name": "헬스 트레이너", "platform": "youtube", "category": "단백질", "followers_range": "50k-200k", "tier": "미드"},
    {"name": "뷰티 크리에이터", "platform": "instagram", "category": "콜라겐", "followers_range": "100k-500k", "tier": "매크로"},
    {"name": "홈트 유튜버", "platform": "youtube", "category": "운동용품", "followers_range": "200k-1M", "tier": "메가"},
    {"name": "맘스타그램", "platform": "instagram", "category": "면역력", "followers_range": "20k-100k", "tier": "마이크로"},
]


def suggest_influencers_for_product(product_name: str, category: str, budget_krw: int = 0) -> Dict:
    """상품에 맞는 인플루언서 매칭 제안"""
    prompt = f"""당신은 한국 인플루언서 마케팅 전문가입니다.
"{product_name}" ({category}) 상품의 SNS 마케팅을 위한 인플루언서 매칭 전략을 제안하세요.

예산: {'₩' + format(budget_krw, ',') if budget_krw else '미정'}

한국에서 실제로 접촉 가능한 인플루언서 카테고리:
- 인스타그램 마이크로 (1-10만): 개당 30-100만원, 진정성 높음
- 인스타그램 미드 (10-50만): 개당 100-500만원, ROI 균형
- 유튜브 미드 (10-50만): 개당 200-800만원, 장기 효과
- 네이버 블로거: 파워블로거 50-300만원/건
- 틱톡 크리에이터: 50-200만원/건

JSON 응답:
{{
  "recommended_tiers": ["가장 적합한 티어 3개"],
  "matching_strategy": "매칭 전략 (2~3문장)",
  "influencer_types": [
    {{
      "type": "유형 (예: 운동 유튜버)",
      "platform": "플랫폼",
      "follower_range": "팔로워 범위",
      "estimated_cost_per_post_krw": 0,
      "why_match": "왜 적합한가",
      "expected_roi": "예상 ROI",
      "outreach_message_template": "접촉 메시지 템플릿 (200자)"
    }}
  ],
  "budget_allocation": {{
    "micro_influencer_pct": 0,
    "mid_influencer_pct": 0,
    "mega_influencer_pct": 0
  }},
  "expected_reach": 0,
  "expected_conversions": 0,
  "campaign_duration_days": 0
}}

JSON만 출력."""

    try:
        from llm_router import call_llm
        raw = call_llm(task_type="copywriting", prompt=prompt, max_tokens=2000)
        import re
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.error(f"인플루언서 매칭 실패: {e}")

    return {"error": True}


# ══════════════════════════════════════════════════════════
# 4. 바이럴 후킹 구조 생성기
# ══════════════════════════════════════════════════════════

def generate_viral_hooks(product_name: str, category: str, count: int = 10) -> Dict:
    """바이럴 후킹 카피 N개 자동 생성"""
    prompt = f"""한국 SNS 바이럴 전문가로서, "{product_name}" ({category}) 상품의 훅 카피 {count}개를 생성하세요.

후킹 패턴:
1. 충격 통계: "한국인 80%가 모르는..."
2. 역설적 질문: "이걸 먹으면 정말..."
3. 개인 경험: "3개월 먹어봤더니..."
4. 전문가 추천: "의사가 추천하는..."
5. 대조: "비싼 것 vs 싼 것"
6. 리스트: "꼭 알아야 할 5가지"
7. 비밀공개: "아무도 말 안 하는"
8. FOMO: "지금 놓치면 후회할"
9. 공감: "나만 이런 줄 알았는데"
10. 반전: "알고 보니..."

한국 법규: 치료/완치/질병 예방 금지, "도움될 수 있어요" 허용

JSON으로 {count}개 생성:
{{
  "hooks": [
    {{
      "type": "패턴명",
      "hook": "훅 카피 (50자 이내)",
      "platform_fit": ["적합한 플랫폼"],
      "emotional_trigger": "감정 트리거"
    }}
  ]
}}

JSON만."""

    try:
        from llm_router import call_llm
        raw = call_llm(task_type="copywriting", prompt=prompt, max_tokens=2000)
        import re
        match = re.search(r'\{[\s\S]*\}', raw)
        if match:
            return json.loads(match.group())
    except Exception as e:
        logger.error(f"훅 생성 실패: {e}")

    return {"hooks": [], "error": True}
