"""
AI 제공자 통합 관리
====================
모든 AI API를 한곳에서 관리

구조:
  Claude  → 텍스트 (카피, 전략, 분석, 컴플라이언스)
  Gemini  → 이미지 (생성, 편집, 번역, 리디자인)
  OpenAI  → (향후) 임베딩, 검색

사용법:
  from ai_providers import ai

  # Claude로 텍스트 작업
  response = ai.claude.messages.create(model=ai.claude_model, ...)

  # Gemini로 이미지 작업
  response = ai.gemini.models.generate_content(model=ai.gemini_model, ...)

  # 비용 추적
  ai.track("claude", input_tokens=1000, output_tokens=500)
  print(ai.cost_report())
"""

import os
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================
# 작업별 AI 라우팅 테이블
# ============================================================

TASK_ROUTING = {
    # 텍스트 작업 → Claude
    "sourcing_analysis":     "claude",
    "pricing":               "rule",      # rule-based, AI 불필요
    "product_registration":  "claude",
    "content_generation":    "claude",
    "compliance_check":      "claude",
    "cs_response":           "claude",
    "keyword_research":      "claude",
    "review_analysis":       "claude",
    "detail_page_copy":      "claude",

    # 이미지 작업 → Gemini
    "image_generation":      "gemini",
    "image_translation":     "gemini",
    "image_redesign":        "gemini",
    "background_removal":    "gemini",
    "detail_page_image":     "gemini",

    # (향후) 검색/임베딩 → OpenAI
    "embedding":             "openai",
    "similarity_search":     "openai",
}


# ============================================================
# 비용 테이블 (2026년 4월 기준)
# ============================================================

COST_TABLE = {
    "claude": {
        "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},   # $/1M tokens
        "claude-haiku-4-5-20251001":  {"input": 0.25, "output": 1.25},
    },
    "gemini": {
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash-preview-image-generation": {"per_image": 0.04},
    },
    "openai": {
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "text-embedding-3-small": {"input": 0.02},
    },
}


@dataclass
class DailyUsage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    images_generated: int = 0
    estimated_cost_usd: float = 0.0


class AIProviderManager:
    """AI 제공자 통합 관리자"""

    def __init__(self):
        self._claude = None
        self._gemini = None
        self._openai = None
        self._usage: Dict[str, DailyUsage] = {}

    # ── Claude ──
    @property
    def claude(self):
        if self._claude is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY 환경변수 필요")
            from anthropic import Anthropic
            self._claude = Anthropic(api_key=api_key)
            logger.info("Claude 클라이언트 초기화 완료")
        return self._claude

    @property
    def claude_model(self) -> str:
        return os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    @property
    def claude_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    # ── Gemini ──
    @property
    def gemini(self):
        if self._gemini is None:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY 환경변수 필요 (https://aistudio.google.com/apikey)")
            from google import genai
            self._gemini = genai.Client(api_key=api_key)
            logger.info("Gemini 클라이언트 초기화 완료")
        return self._gemini

    @property
    def gemini_model(self) -> str:
        return os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    @property
    def gemini_image_model(self) -> str:
        return os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

    @property
    def gemini_available(self) -> bool:
        return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

    # ── OpenAI (향후) ──
    @property
    def openai(self):
        if self._openai is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY 환경변수 필요")
            from openai import OpenAI
            self._openai = OpenAI(api_key=api_key)
            logger.info("OpenAI 클라이언트 초기화 완료")
        return self._openai

    @property
    def openai_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    # ── 작업 라우팅 ──
    def get_provider_for(self, task: str) -> str:
        """작업에 맞는 AI 제공자 반환"""
        return TASK_ROUTING.get(task, "claude")

    # ── 비용 추적 ──
    def track(self, provider: str, input_tokens: int = 0, output_tokens: int = 0, images: int = 0):
        """API 사용량 기록"""
        today = date.today().isoformat()
        key = f"{provider}_{today}"

        if key not in self._usage:
            self._usage[key] = DailyUsage()

        u = self._usage[key]
        u.calls += 1
        u.input_tokens += input_tokens
        u.output_tokens += output_tokens
        u.images_generated += images

        # 비용 추정
        if provider == "claude":
            model_costs = COST_TABLE["claude"].get(self.claude_model, {"input": 3.0, "output": 15.0})
            cost = (input_tokens * model_costs["input"] + output_tokens * model_costs["output"]) / 1_000_000
        elif provider == "gemini":
            if images > 0:
                cost = images * 0.04
            else:
                model_costs = COST_TABLE["gemini"].get(self.gemini_model, {"input": 0.075, "output": 0.30})
                cost = (input_tokens * model_costs["input"] + output_tokens * model_costs["output"]) / 1_000_000
        else:
            cost = 0

        u.estimated_cost_usd += cost

    def cost_report(self) -> str:
        """비용 리포트"""
        today = date.today().isoformat()
        lines = [f"AI 비용 리포트 ({today})", ""]

        total_cost = 0
        for key, usage in sorted(self._usage.items()):
            if today in key:
                provider = key.split("_")[0]
                lines.append(f"  {provider}: {usage.calls}건 | "
                           f"토큰: {usage.input_tokens:,}in/{usage.output_tokens:,}out | "
                           f"이미지: {usage.images_generated} | "
                           f"비용: ${usage.estimated_cost_usd:.4f}")
                total_cost += usage.estimated_cost_usd

        lines.append(f"\n  오늘 합계: ${total_cost:.4f} (≈₩{total_cost * 1380:.0f})")
        return "\n".join(lines)

    def status(self) -> Dict:
        """제공자 상태 확인"""
        return {
            "claude": {"available": self.claude_available, "model": self.claude_model},
            "gemini": {"available": self.gemini_available, "model": self.gemini_model},
            "openai": {"available": self.openai_available},
        }


# ============================================================
# 글로벌 인스턴스
# ============================================================

ai = AIProviderManager()


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    print("\nFortimove AI 제공자 상태")
    print("=" * 50)

    status = ai.status()
    for provider, info in status.items():
        available = "✅" if info["available"] else "❌"
        model = info.get("model", "")
        print(f"  {available} {provider:<10} {model}")

    print("\n작업별 라우팅:")
    for task, provider in TASK_ROUTING.items():
        print(f"  {task:<25} → {provider}")

    print(f"\n비용 테이블:")
    for provider, models in COST_TABLE.items():
        for model, costs in models.items():
            if "input" in costs:
                print(f"  {provider}/{model}: ${costs['input']}/1M input, ${costs.get('output', 0)}/1M output")
            elif "per_image" in costs:
                print(f"  {provider}/{model}: ${costs['per_image']}/image")
