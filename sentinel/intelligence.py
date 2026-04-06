"""
Sentinel Intelligence Engine — Executive-Grade Analysis

분석 수준: 대기업 경영진 브리핑 퀄리티
- 적합도 0% 아이템 발송 차단
- D-day 30일+ 공고 우선
- 직접 해당 아니어도 참고 가치 있으면 "참고" 등급 부여
- 자금줄 가능성 판단
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config import COMPANY_PROFILE, GOOGLE_API_KEY

logger = logging.getLogger(__name__)


def _call_llm(prompt: str, max_tokens: int = 2000) -> str:
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        return response.text or ""
    except Exception as e:
        logger.error(f"LLM 호출 실패: {e}")
        return ""


def analyze_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """Executive-grade 단일 아이템 분석"""

    # ── 1. 긴급도 산출 ────────────────────────────
    urgency = _calc_urgency(item.get("deadline", ""))

    # ── 2. LLM 분석 (고품질 프롬프트) ─────────────
    current_date = datetime.now().strftime("%Y-%m-%d")
    current_year = datetime.now().year
    current_month = datetime.now().month

    prompt = f"""당신은 연매출 1000억 이상 기업의 전략기획실장입니다.
현재 날짜: {current_date} ({current_year}년 {current_month}월)
분석 기준: {current_year}년 현재 시점에서 즉시 활용 가능한 정보인지 판단하세요.
과거 연도(2025년 이하)의 사업/공고는 "만료됨"으로 처리하세요.
CEO에게 보고할 인텔리전스 분석을 작성하세요.

## 분석 대상
제목: {item.get('title', '')}
출처: {item.get('source', '')}
카테고리: {item.get('category', '')}
URL: {item.get('url', '')}
마감일: {item.get('deadline', '미정')}
본문: {item.get('body', '')[:800]}

## CEO 기업 프로필
- 회사명: {COMPANY_PROFILE['name']}
- 업종: {COMPANY_PROFILE['business_type']}
- 산업: {', '.join(COMPANY_PROFILE['industry'])}
- 소재지: {COMPANY_PROFILE['location']}
- 인원: {COMPANY_PROFILE['employee_count']}명
- CEO 분류: {COMPANY_PROFILE['ceo_age_group']} 창업자
- 현재 단계: {COMPANY_PROFILE.get('current_stage', '')}
- 비전: {COMPANY_PROFILE.get('vision', '')}

## 분석 기준
1. **적합도 판단**: 이 정보가 CEO의 사업에 직접 해당하는가?
   - 0.8~1.0: 직접 신청/활용 가능 (구매대행, 이커머스, 웰니스, 수원/경기, 청년창업, 1인기업)
   - 0.5~0.7: 간접 관련 — 참고/벤치마킹 가치 있음 (타 지역이지만 유사 사업, 업계 동향)
   - 0.2~0.4: 약한 관련성 — 업계 트렌드 파악용
   - 0.0~0.1: 무관 (자동차, 농업, 건설 등 완전 다른 산업)

2. **자금줄 가능성**: 이 지원사업에 실제 신청하여 자금을 확보할 수 있는가?
   - "HIGH": 신청 자격 충족 가능성 높음 + 지원 금액 의미 있음
   - "MEDIUM": 자격 일부 충족 또는 추가 조건 필요
   - "LOW": 자격 미충족이지만 향후 가능
   - "NONE": 해당 없음 (뉴스/규제 정보)
   - "REFERENCE": 직접 해당은 아니지만 경영 판단에 참고할 가치 있음

3. **액션 분류**:
   - "APPLY_NOW": 즉시 서류 준비 착수
   - "PREPARE": 자격 조건 갖추기 (사전 준비)
   - "WATCH": 모니터링 유지 (추가 정보 대기)
   - "LEARN": 벤치마킹/학습 가치
   - "DISMISS": 무관 — 발송하지 마라

## 출력 (JSON만)
{{
  "summary": "핵심 3줄 요약 (1.무엇인가 2.CEO에게 왜 중요한가 3.예상 이득/영향)",
  "relevance_score": 0.0~1.0,
  "relevance_reason": "적합/부적합 판단 근거 1문장",
  "funding_potential": "HIGH/MEDIUM/LOW/NONE/REFERENCE",
  "funding_detail": "자금 확보 가능성 근거 (금액, 조건, 일정 포함)",
  "amount_estimate": "지원 금액 (예: '최대 5천만원', '수수료 6%→5%로 절감 예상', '미상')",
  "action": "APPLY_NOW/PREPARE/WATCH/LEARN/DISMISS",
  "action_detail": "CEO가 이번 주 내에 해야 할 구체적 행동 1-2문장",
  "executive_insight": "경영진 관점 인사이트 1문장 (시장 흐름, 경쟁 포지셔닝, 기회/위험 관점)",
  "risk_note": "주의사항 또는 [확인 필요] 사항 (없으면 빈 문자열)"
}}"""

    try:
        response = _call_llm(prompt, max_tokens=1200)
        raw = response.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        analysis = json.loads(raw)
    except Exception as e:
        logger.warning(f"LLM 분석 실패: {e}")
        analysis = {
            "summary": item.get("title", ""),
            "relevance_score": 0.1,
            "relevance_reason": "자동 분석 실패",
            "funding_potential": "NONE",
            "funding_detail": "",
            "amount_estimate": "미상",
            "action": "DISMISS",
            "action_detail": "수동 확인 필요",
            "executive_insight": "",
            "risk_note": "",
        }

    # ── 3. 결과 합성 ─────────────────────────────
    relevance = analysis.get("relevance_score", 0)
    action = analysis.get("action", "DISMISS")

    # DISMISS면 발송 차단 (적합도 0.1 이하로 설정)
    if action == "DISMISS":
        relevance = 0.05

    item["summary"] = analysis.get("summary", "")
    item["eligibility_match"] = relevance
    item["amount"] = analysis.get("amount_estimate", "")
    item["urgency"] = urgency
    item["funding_potential"] = analysis.get("funding_potential", "NONE")
    item["funding_detail"] = analysis.get("funding_detail", "")
    item["executive_insight"] = analysis.get("executive_insight", "")
    item["risk_note"] = analysis.get("risk_note", "")

    # 액션 제안 (한국어)
    action_kr = {
        "APPLY_NOW": "즉시 신청 준비",
        "PREPARE": "자격 조건 사전 준비",
        "WATCH": "모니터링 유지",
        "LEARN": "참고/벤치마킹",
        "DISMISS": "무관",
    }
    item["action_suggestion"] = (
        f"[{action_kr.get(action, action)}] "
        f"{analysis.get('action_detail', '')}"
    )

    # 긴급도 재조정
    if action == "APPLY_NOW" and relevance >= 0.7:
        item["urgency"] = "critical" if urgency in ("critical", "high") else "high"
    elif relevance < 0.2:
        item["urgency"] = "low"

    return item


def _calc_urgency(deadline: str) -> str:
    if not deadline:
        return "medium"
    try:
        dl = datetime.strptime(deadline.replace(".", "-"), "%Y-%m-%d")
        days_left = (dl - datetime.now()).days
        if days_left < 0:
            return "low"
        elif days_left <= 3:
            return "critical"
        elif days_left <= 7:
            return "high"
        elif days_left <= 30:
            return "medium"
        else:
            return "low"
    except ValueError:
        return "medium"


def batch_analyze(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """일괄 분석 + 품질 필터링"""
    analyzed = []
    for i, item in enumerate(items):
        logger.info(f"  분석 중 ({i+1}/{len(items)}): {item['title'][:40]}")
        result = analyze_item(item)
        analyzed.append(result)

    # 품질 필터: 적합도 0.15 이하 제거 (발송 대상에서 제외)
    quality_items = [a for a in analyzed if a.get("eligibility_match", 0) >= 0.15]
    filtered_count = len(analyzed) - len(quality_items)

    if filtered_count > 0:
        logger.info(f"  품질 필터: {filtered_count}건 제거 (적합도 15% 미만)")

    # 적합도 높은 순 + 긴급도 순 정렬
    urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    quality_items.sort(key=lambda x: (
        urgency_order.get(x.get("urgency", "low"), 3),
        -x.get("eligibility_match", 0)
    ))

    return quality_items


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_item = {
        "item_id": "test001",
        "source": "bizinfo",
        "category": "funding",
        "title": "2026년 수원시 청년 이커머스 창업 지원사업 모집",
        "url": "https://example.com",
        "deadline": "2026-05-15",
        "keywords": ["수원", "청년창업", "이커머스"],
        "body": "수원시에서 청년 이커머스 창업자를 대상으로 사업화 자금 최대 3천만원, 멘토링, 사무공간을 지원합니다.",
    }

    result = analyze_item(test_item)
    print(json.dumps({k: v for k, v in result.items() if k not in ("raw_data", "body")}, ensure_ascii=False, indent=2))
