"""
Application Drafter — 지원사업 신청서 초안 자동 작성

지원사업 공고 내용 + 기업 프로필 → 신청서 초안 생성
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict

from config import COMPANY_PROFILE, GOOGLE_API_KEY

logger = logging.getLogger(__name__)


def draft_application(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    지원사업 신청서 초안 생성

    Args:
        item: intel_items 테이블의 아이템 (title, summary, url, category 등)

    Returns:
        {
            "title": "신청서 제목",
            "company_intro": "기업 소개 (300자)",
            "business_plan": "사업 계획 요약 (500자)",
            "expected_outcome": "기대 효과 (300자)",
            "budget_plan": "예산 활용 계획",
            "eligibility_checklist": ["자격 요건 체크리스트"],
            "documents_needed": ["필요 서류 목록"],
            "tips": "신청 전략/팁",
        }
    """
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GOOGLE_API_KEY)

        current_date = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""당신은 정부 지원사업 신청 전문 컨설턴트입니다.
아래 지원사업에 대한 신청서 초안을 작성하세요.

## 지원사업 정보
제목: {item.get('title', '')}
요약: {item.get('summary', '')}
마감일: {item.get('deadline', '미정')}
URL: {item.get('url', '')}

## 신청 기업 정보
기업명: {COMPANY_PROFILE['name']}
업종: {COMPANY_PROFILE['business_type']}
산업: {', '.join(COMPANY_PROFILE['industry'])}
소재지: {COMPANY_PROFILE['location']}
인원: {COMPANY_PROFILE['employee_count']}명
설립: {COMPANY_PROFILE['founded_year']}년
CEO: {COMPANY_PROFILE['ceo_age_group']} 창업자
현재 단계: {COMPANY_PROFILE.get('current_stage', '')}
비전: {COMPANY_PROFILE.get('vision', '')}
오늘 날짜: {current_date}

## 작성 지침
1. 기업 소개는 지원사업 목적에 맞춰 강조점을 조정하세요
2. 사업 계획은 구체적 수치와 일정을 포함하세요
3. 수원/경기 지역 가점이 있다면 반드시 언급하세요
4. 청년/1인기업 가점이 있다면 반드시 언급하세요
5. 과장 없이 사실에 기반하되, 성장 가능성을 강조하세요

## 출력 (JSON)
{{
  "title": "신청서 제목",
  "company_intro": "기업 소개 (300자 내외, 복사 가능한 완성형)",
  "business_plan": "사업 계획 요약 (500자 내외, 복사 가능한 완성형)",
  "expected_outcome": "기대 효과 및 성과 목표 (300자 내외)",
  "budget_plan": "예산 활용 계획 (항목별)",
  "eligibility_checklist": ["자격 요건 1: 충족/미충족/확인필요", ...],
  "documents_needed": ["필요 서류 1", "필요 서류 2", ...],
  "tips": "이 지원사업 신청 전략 및 주의사항 (200자)"
}}

JSON만 반환하세요."""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=3000,
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        raw = (response.text or "").strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        draft = json.loads(raw)
        draft["source_item_id"] = item.get("item_id", "")
        draft["source_title"] = item.get("title", "")
        draft["generated_at"] = datetime.now().isoformat()

        return draft

    except Exception as e:
        logger.error(f"신청서 초안 생성 실패: {e}")
        return {
            "title": item.get("title", ""),
            "error": str(e),
            "company_intro": "",
            "business_plan": "",
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test = {
        "item_id": "test",
        "title": "2026년 수원시 청년 이커머스 창업 지원사업",
        "summary": "수원시에서 청년 이커머스 창업자를 대상으로 사업화 자금 최대 3천만원, 멘토링, 사무공간 지원",
        "deadline": "2026-05-15",
        "url": "https://example.com",
    }

    result = draft_application(test)
    print(json.dumps(result, ensure_ascii=False, indent=2))
