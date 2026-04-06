"""
LLM Router — 작업 유형별 최적 API 자동 라우팅

전략:
┌─────────────────────────────────────────────────────────────────────┐
│  작업 유형              │ 최적 API          │ 이유                   │
│─────────────────────────┼───────────────────┼────────────────────────│
│  리스크 분석/컴플라이언스 │ Claude            │ 추론 + 한국법 이해     │
│  PM 의도 파악/라우팅     │ Claude            │ 복잡한 의도 분석       │
│  CS 응대 템플릿         │ Claude            │ 뉘앙스 + 안전성        │
│  한국어 카피라이팅       │ Gemini Flash      │ 빠름 + 비용 효율       │
│  SEO 메타데이터         │ Gemini Flash      │ 정형화된 출력          │
│  상세페이지 텍스트       │ Gemini Flash      │ 창의성 + 속도          │
│  번역 (중→한)           │ Gemini Flash      │ 다국어 + 비용 효율     │
│  이미지 생성            │ Imagen 4.0        │ 비주얼 품질            │
│  마진 계산              │ Rule-based        │ LLM 불필요             │
│  스코어링               │ Rule-based        │ LLM 불필요             │
└─────────────────────────────────────────────────────────────────────┘
"""

import logging
import os
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# .env 자동 로드 (llm_router가 다른 모듈보다 먼저 import 될 수 있음)
try:
    from dotenv import load_dotenv
    _env_dir = Path(__file__).parent
    load_dotenv(_env_dir / ".env")
    load_dotenv(_env_dir.parent / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ── FinOps: 토큰/비용 추적 ───────────────────────────────

# 가격 (USD per 1M tokens, 2026-04 기준)
_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "imagen-4.0-fast-generate-001": {"per_image": 0.02},
}

_FINOPS_DB = str(__import__('pathlib').Path(__file__).parent / "data" / "approval_queue.db")
_finops_lock = threading.Lock()


def _init_finops_table():
    """FinOps 테이블 초기화"""
    with sqlite3.connect(_FINOPS_DB) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_usage_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            task_type TEXT NOT NULL,
            agent_name TEXT DEFAULT '',
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            cost_usd REAL DEFAULT 0,
            cost_krw REAL DEFAULT 0,
            prompt_length INTEGER DEFAULT 0,
            response_length INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_message TEXT DEFAULT ''
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS ai_budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            month TEXT NOT NULL UNIQUE,
            budget_krw REAL DEFAULT 100000,
            spent_krw REAL DEFAULT 0,
            alert_threshold REAL DEFAULT 0.8
        )''')
        conn.commit()

_init_finops_table()

_current_task_type = ""
_current_agent_name = ""


def _log_usage(provider: str, model: str, input_tokens: int, output_tokens: int, success: bool = True, error: str = "", prompt_len: int = 0, response_len: int = 0):
    """AI 사용량 로깅"""
    pricing = _PRICING.get(model, {})
    cost_usd = (input_tokens * pricing.get("input", 0) + output_tokens * pricing.get("output", 0)) / 1_000_000
    if "imagen" in model:
        cost_usd = pricing.get("per_image", 0.02)
    cost_krw = cost_usd * 1450  # USD→KRW

    with _finops_lock:
        try:
            with sqlite3.connect(_FINOPS_DB) as conn:
                conn.execute('''INSERT INTO ai_usage_log
                    (timestamp, provider, model, task_type, agent_name, input_tokens, output_tokens, total_tokens, cost_usd, cost_krw, prompt_length, response_length, success, error_message)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (datetime.now().isoformat(), provider, model, _current_task_type, _current_agent_name,
                     input_tokens, output_tokens, input_tokens + output_tokens,
                     round(cost_usd, 6), round(cost_krw, 2), prompt_len, response_len,
                     1 if success else 0, error))
                # 월별 예산 업데이트
                month = datetime.now().strftime('%Y-%m')
                conn.execute('INSERT OR IGNORE INTO ai_budget (month) VALUES (?)', (month,))
                conn.execute('UPDATE ai_budget SET spent_krw = spent_krw + ? WHERE month = ?', (round(cost_krw, 2), month))
                conn.commit()
        except Exception as e:
            logger.warning(f"FinOps 로깅 실패: {e}")

# ── API 키 ────────────────────────────────────────────────

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if not ANTHROPIC_API_KEY:
    logger.warning("ANTHROPIC_API_KEY 환경변수 미설정 — Claude 호출 실패 가능")
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY 환경변수 미설정 — Gemini 호출 실패 가능")

# ── 모델 설정 ─────────────────────────────────────────────

MODELS = {
    # Claude — 추론/분석/컴플라이언스 (정확도 우선)
    "claude_reasoning": "claude-sonnet-4-20250514",

    # Gemini Flash — 생성/번역/SEO (속도+비용 우선)
    "gemini_fast": "gemini-2.5-flash",

    # Imagen — 이미지 생성
    "imagen": "imagen-4.0-fast-generate-001",
}

# ── 작업별 라우팅 테이블 ──────────────────────────────────

TASK_ROUTING = {
    # Claude 전용 (추론/안전성 필수)
    "risk_analysis":       "claude",    # 소싱 리스크 분석
    "compliance_check":    "claude",    # 컴플라이언스 검증
    "pm_intent":           "claude",    # PM 의도 파악/라우팅
    "cs_response":         "claude",    # CS 응대 (법적 뉘앙스)
    "legal_check":         "claude",    # 법령 검토

    # 텍스트 생성 (Claude — Google API 키 유출로 Gemini 비활성)
    "content_generation":  "claude",    # 상품 콘텐츠 일괄 생성
    "copywriting":         "claude",    # 한국어 카피라이팅
    "seo_metadata":        "claude",    # SEO 메타데이터 생성
    "translation":         "claude",    # 중→한 번역
    "detail_page_text":    "claude",    # 상세페이지 텍스트
    "sns_content":         "claude",    # SNS/블로그 콘텐츠
    "ad_copy":             "claude",    # 광고 문구
    "product_summary":     "claude",    # 상품 요약

    # Imagen (이미지)
    "image_generation":    "imagen",    # 이미지 생성

    # Rule-based (LLM 불필요)
    "margin_calc":         "rule",      # 마진 계산
    "scoring":             "rule",      # 스코어링
    "auto_approval":       "rule",      # 자동 승인
}


# ── 클라이언트 캐시 ───────────────────────────────────────

_claude_client = None
_gemini_client = None


def _get_claude():
    global _claude_client
    if _claude_client is None:
        from anthropic import Anthropic
        _claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _claude_client


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=GOOGLE_API_KEY)
    return _gemini_client


# ── 통합 호출 인터페이스 ──────────────────────────────────

def call_llm(
    task_type: str,
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """
    작업 유형에 따라 최적 API를 자동 선택하여 호출.

    Args:
        task_type: TASK_ROUTING 키 (예: "copywriting", "risk_analysis")
        prompt: 사용자/에이전트 프롬프트
        system_prompt: 시스템 프롬프트
        max_tokens: 최대 토큰
        temperature: 생성 온도

    Returns:
        LLM 응답 텍스트
    """
    global _current_task_type
    _current_task_type = task_type

    route = TASK_ROUTING.get(task_type, "claude")

    if route == "rule":
        raise ValueError(f"'{task_type}'는 Rule-based 작업입니다. LLM 호출 불필요.")

    if route == "gemini":
        return _call_gemini(prompt, system_prompt, max_tokens, temperature)
    elif route == "imagen":
        raise ValueError("이미지 생성은 call_llm이 아닌 generate_image()를 사용하세요.")
    else:
        return _call_claude(prompt, system_prompt, max_tokens, temperature)


def _call_claude(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Claude API 호출"""
    try:
        client = _get_claude()
        kwargs: Dict[str, Any] = {
            "model": MODELS["claude_reasoning"],
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if temperature != 0.7:
            kwargs["temperature"] = temperature

        response = client.messages.create(**kwargs)
        result = response.content[0].text
        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        logger.debug(f"[Claude] {len(result)} chars, {in_tok}+{out_tok} tokens")
        _log_usage("anthropic", MODELS["claude_reasoning"], in_tok, out_tok, prompt_len=len(prompt), response_len=len(result))
        return result

    except Exception as e:
        logger.warning(f"[Claude] 실패: {e} — Gemini 폴백 시도")
        _log_usage("anthropic", MODELS["claude_reasoning"], 0, 0, success=False, error=str(e)[:200], prompt_len=len(prompt))
        return _call_gemini(prompt, system_prompt, max_tokens, temperature)


def _call_gemini(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Gemini Flash API 호출"""
    try:
        from google.genai import types
        client = _get_gemini()

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

        response = client.models.generate_content(
            model=MODELS["gemini_fast"],
            contents=full_prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        result = response.text or ""
        # Gemini usage 추정 (정확한 토큰 수는 API에서 제공하지 않을 수 있음)
        in_tok_est = len(full_prompt) // 4
        out_tok_est = len(result) // 4
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                in_tok_est = getattr(response.usage_metadata, 'prompt_token_count', in_tok_est)
                out_tok_est = getattr(response.usage_metadata, 'candidates_token_count', out_tok_est)
        except Exception:
            pass
        logger.debug(f"[Gemini] {len(result)} chars, ~{in_tok_est}+{out_tok_est} tokens")
        _log_usage("google", MODELS["gemini_fast"], in_tok_est, out_tok_est, prompt_len=len(prompt), response_len=len(result))
        return result

    except Exception as e:
        logger.warning(f"[Gemini] 실패: {e} — Claude 폴백 시도")
        _log_usage("google", MODELS["gemini_fast"], 0, 0, success=False, error=str(e)[:200], prompt_len=len(prompt))
        # Gemini 실패 시 Claude로 폴백
        try:
            return _call_claude_direct(prompt, system_prompt, max_tokens, temperature)
        except Exception as e2:
            logger.error(f"[Fallback] 모든 API 실패: {e2}")
            raise


def _call_claude_direct(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Claude 직접 호출 (폴백 전용, 재귀 방지)"""
    client = _get_claude()
    kwargs: Dict[str, Any] = {
        "model": MODELS["claude_reasoning"],
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    response = client.messages.create(**kwargs)
    return response.content[0].text


# ── Vision 분석 (이미지 → 텍스트) ─────────────────────────

def call_llm_with_images(
    task_type: str,
    prompt: str,
    image_urls: list,
    max_tokens: int = 1500,
) -> str:
    """이미지 + 텍스트 프롬프트 → 텍스트 응답 (Vision)

    Gemini Vision 사용 (비용 효율)
    """
    try:
        import requests as _req
        from google.genai import types

        client = _get_gemini()

        # 이미지 다운로드 (최대 3장)
        image_parts = []
        for url in image_urls[:3]:
            try:
                r = _req.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and len(r.content) > 1000:
                    mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
                    if "image" not in mime:
                        mime = "image/jpeg"
                    image_parts.append(types.Part.from_bytes(data=r.content, mime_type=mime))
            except Exception as e:
                logger.warning(f"이미지 다운로드 실패 {url[:60]}: {e}")

        if not image_parts:
            raise ValueError("다운로드 가능한 이미지 없음")

        contents = image_parts + [prompt]

        response = client.models.generate_content(
            model=MODELS["gemini_fast"],
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.3,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        result = response.text or ""

        # 비용 로깅
        in_tok = len(prompt) // 4 + len(image_parts) * 250
        out_tok = len(result) // 4
        try:
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                in_tok = getattr(response.usage_metadata, 'prompt_token_count', in_tok)
                out_tok = getattr(response.usage_metadata, 'candidates_token_count', out_tok)
        except Exception:
            pass
        _log_usage("google", MODELS["gemini_fast"], in_tok, out_tok, prompt_len=len(prompt), response_len=len(result))

        logger.info(f"[Vision] {len(image_parts)}장 분석 완료, {len(result)} chars")
        return result
    except Exception as e:
        logger.error(f"Vision 분석 실패: {e}")
        _log_usage("google", MODELS["gemini_fast"], 0, 0, success=False, error=str(e)[:200])
        raise


# ── 이미지 생성 인터페이스 ────────────────────────────────

def generate_image(prompt: str, output_path: str) -> bool:
    """Imagen 4.0으로 이미지 생성"""
    try:
        from google.genai import types
        client = _get_gemini()

        result = client.models.generate_images(
            model=MODELS["imagen"],
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/jpeg",
            ),
        )

        if result.generated_images:
            with open(output_path, "wb") as f:
                f.write(result.generated_images[0].image.image_bytes)
            return True
        return False

    except Exception as e:
        logger.error(f"[Imagen] 이미지 생성 실패: {e}")
        return False


# ── 유틸 ──────────────────────────────────────────────────

def get_routing_info() -> Dict[str, str]:
    """현재 라우팅 설정 반환"""
    return {task: route for task, route in TASK_ROUTING.items()}


def get_api_status() -> Dict[str, bool]:
    """각 API 사용 가능 여부"""
    return {
        "claude": bool(ANTHROPIC_API_KEY),
        "gemini": bool(GOOGLE_API_KEY),
        "imagen": bool(GOOGLE_API_KEY),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=== LLM Router Status ===")
    print(f"\nAPI 상태: {get_api_status()}")
    print(f"\n라우팅 테이블:")
    for task, route in TASK_ROUTING.items():
        print(f"  {task:25s} → {route}")

    # Gemini 테스트
    print("\n=== Gemini Flash 테스트 ===")
    result = call_llm(
        task_type="copywriting",
        prompt="다음 상품의 판매 카피를 3개 작성하세요: 프리미엄 비타민 C 1000mg. 한국 이커머스 톤으로 작성.",
        max_tokens=500,
    )
    print(result[:300])
