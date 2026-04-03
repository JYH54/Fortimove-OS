"""
Gemini 이미지 생성/편집 모듈
=============================
Google Gemini API를 활용한 이미지 생성 및 편집

역할 분리:
  - Claude: 텍스트 (카피, 전략, 분석, 컴플라이언스)
  - Gemini: 이미지 (생성, 편집, 번역, 리디자인)

기능:
  1. 상세페이지 섹션 이미지 생성 (히어로, 혜택, FAQ 등)
  2. 상품 이미지 리디자인 (중국어→한국어 텍스트 교체)
  3. 배경 교체/개선
  4. 상품 이미지 + 텍스트 합성

필요:
  pip install google-genai
  GEMINI_API_KEY=... (.env에 추가)
"""

import os
import io
import json
import base64
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

# Gemini 클라이언트 (lazy init)
_gemini_client = None


def _get_client():
    """Gemini 클라이언트 초기화"""
    global _gemini_client
    if _gemini_client:
        return _gemini_client

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY 환경변수가 필요합니다.\n"
            "https://aistudio.google.com/apikey 에서 발급받으세요."
        )

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=api_key)
        logger.info("Gemini API 클라이언트 초기화 완료")
        return _gemini_client
    except ImportError:
        raise ImportError("google-genai 패키지 필요: pip install google-genai")


def _image_to_bytes(image: Image.Image, format: str = "PNG") -> bytes:
    """PIL Image → bytes"""
    buf = io.BytesIO()
    image.save(buf, format=format)
    return buf.getvalue()


def _bytes_to_image(data: bytes) -> Image.Image:
    """bytes → PIL Image"""
    return Image.open(io.BytesIO(data))


def _save_image(image: Image.Image, path: str):
    """이미지 저장"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    image.save(path, "PNG", quality=95)


# ============================================================
# 1. 상세페이지 섹션 이미지 생성
# ============================================================

def generate_detail_section(
    section_type: str,
    text_content: str,
    product_name: str = "",
    style: str = "premium",
    width: int = 860,
    height: int = 400,
) -> Optional[Image.Image]:
    """
    상세페이지 섹션 이미지 생성

    section_type: hero_banner, benefits, problem_solution, faq, cta, specs
    """
    client = _get_client()
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

    style_desc = {
        "premium": "깔끔하고 고급스러운 느낌, 보라색+흰색 배색, 모던 미니멀 디자인",
        "clean": "밝고 깨끗한 느낌, 흰색 배경 위주, 심플한 레이아웃",
        "warm": "따뜻한 느낌, 베이지+브라운 톤, 자연스러운 텍스처",
        "minimal": "극도로 심플, 흑백 위주, 타이포그래피 중심",
    }

    section_prompts = {
        "hero_banner": f"""한국 이커머스 상세페이지 히어로 배너 이미지를 만들어주세요.

상품: {product_name}
텍스트: {text_content}

디자인 요구사항:
- {width}x{height}px 사이즈
- {style_desc.get(style, style_desc['premium'])}
- 텍스트가 크고 선명하게 중앙 배치
- 한국어 텍스트 사용
- 상품 상세페이지 최상단에 들어갈 매력적인 배너
- 배경은 그라데이션 또는 깔끔한 단색""",

        "benefits": f"""한국 이커머스 상세페이지 혜택 섹션 이미지를 만들어주세요.

상품: {product_name}
혜택 내용:
{text_content}

디자인 요구사항:
- {width}x{height}px 사이즈
- {style_desc.get(style, style_desc['premium'])}
- 각 혜택 항목에 체크 아이콘 또는 심플한 아이콘 배치
- 한국어 텍스트, 가독성 좋게
- 이커머스 상세페이지에 바로 넣을 수 있는 완성도""",

        "faq": f"""한국 이커머스 상세페이지 FAQ 섹션 이미지를 만들어주세요.

상품: {product_name}
FAQ 내용:
{text_content}

디자인 요구사항:
- {width}x{height}px 사이즈
- Q&A 형식이 명확하게 구분
- 깔끔한 카드 형태 레이아웃
- 한국어 텍스트
- {style_desc.get(style, style_desc['premium'])}""",

        "cta": f"""한국 이커머스 상세페이지 구매 유도(CTA) 배너 이미지를 만들어주세요.

상품: {product_name}
텍스트: {text_content}

디자인 요구사항:
- {width}x200px 사이즈
- 강렬한 컬러 (주황색 또는 빨간색 계열)
- "지금 바로 구매" 느낌의 긴급감
- 한국어 텍스트, 큰 폰트
- 하단에 작게: "※ 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다" 포함""",
    }

    prompt = section_prompts.get(section_type, section_prompts["hero_banner"])

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config={
                "response_modalities": ["image", "text"],
                "image_generation": {"number_of_images": 1},
            }
        )

        # 응답에서 이미지 추출
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                image_data = part.inline_data.data
                return _bytes_to_image(image_data)

        logger.warning(f"Gemini 응답에 이미지 없음 (section: {section_type})")
        return None

    except Exception as e:
        logger.error(f"Gemini 이미지 생성 실패: {e}")
        return None


# ============================================================
# 2. 상품 이미지 리디자인
# ============================================================

def redesign_product_image(
    image: Image.Image,
    instruction: str,
    product_name: str = "",
) -> Optional[Image.Image]:
    """
    기존 상품 이미지를 리디자인

    instruction 예시:
    - "중국어 텍스트를 한국어로 변환해주세요"
    - "배경을 깔끔한 흰색으로 교체해주세요"
    - "이미지 톤을 프리미엄하게 보정해주세요"
    """
    client = _get_client()
    model = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-preview-image-generation")

    image_bytes = _image_to_bytes(image)

    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                {
                    "parts": [
                        {"text": f"""이 상품 이미지를 한국 이커머스용으로 리디자인해주세요.

상품: {product_name}
요청: {instruction}

중요:
- 상품 자체는 그대로 유지
- 텍스트만 한국어로 교체
- 전체적으로 깔끔하고 프리미엄한 느낌으로
- 이커머스 상세페이지에 바로 쓸 수 있는 퀄리티"""},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": base64.b64encode(image_bytes).decode()
                            }
                        }
                    ]
                }
            ],
            config={
                "response_modalities": ["image", "text"],
                "image_generation": {"number_of_images": 1},
            }
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, 'inline_data') and part.inline_data:
                return _bytes_to_image(part.inline_data.data)

        return None

    except Exception as e:
        logger.error(f"Gemini 리디자인 실패: {e}")
        return None


def translate_image(
    image: Image.Image,
    source_lang: str = "중국어",
    target_lang: str = "한국어",
    product_name: str = "",
) -> Optional[Image.Image]:
    """이미지 내 텍스트를 번역하여 새 이미지 생성"""
    return redesign_product_image(
        image,
        instruction=f"이미지 내의 {source_lang} 텍스트를 모두 {target_lang}로 자연스럽게 번역해주세요. "
                    f"폰트 스타일과 레이아웃은 최대한 유지하되, {target_lang}에 맞게 조정해주세요.",
        product_name=product_name,
    )


def remove_background_gemini(
    image: Image.Image,
    new_bg: str = "깔끔한 흰색 배경",
) -> Optional[Image.Image]:
    """배경 교체"""
    return redesign_product_image(
        image,
        instruction=f"상품만 남기고 배경을 {new_bg}으로 교체해주세요. 상품 자체는 변경하지 마세요.",
    )


# ============================================================
# 3. 전체 상세페이지 이미지 세트 생성
# ============================================================

def generate_full_detail_page(
    premium_result: Dict,
    output_dir: str = "detail_images",
    style: str = "premium",
) -> List[str]:
    """
    premium_detail_page 결과를 Gemini로 섹션별 이미지 생성

    Returns: 생성된 이미지 파일 경로 리스트
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []

    hooks = premium_result.get("hook_copies", [])
    sections = premium_result.get("naver_detail_page", {}).get("sections", [])
    faq = premium_result.get("faq", [])
    titles = premium_result.get("product_titles", {})
    product_name = titles.get("smartstore", "")

    # 1. 히어로 배너
    if hooks:
        print("    [1] 히어로 배너 생성 중...", end=" ", flush=True)
        hook_text = "\n".join(hooks[:3])
        img = generate_detail_section("hero_banner", hook_text, product_name, style)
        if img:
            path = os.path.join(output_dir, "01_hero_banner.png")
            _save_image(img, path)
            generated.append(path)
            print("완료")
        else:
            print("실패 (Pillow fallback 사용)")
            # Pillow fallback
            from detail_image_generator import generate_hero_banner
            img = generate_hero_banner(hooks, product_name)
            path = os.path.join(output_dir, "01_hero_banner.png")
            img.save(path, "PNG")
            generated.append(path)

    # 2. 혜택 섹션
    benefits_text = ""
    for section in sections:
        name = section.get("section_name", "").lower()
        if "혜택" in name or "좋습니다" in name:
            benefits_text = section.get("content", "")
            break

    if benefits_text:
        print("    [2] 혜택 섹션 생성 중...", end=" ", flush=True)
        img = generate_detail_section("benefits", benefits_text, product_name, style, height=500)
        if img:
            path = os.path.join(output_dir, "02_benefits.png")
            _save_image(img, path)
            generated.append(path)
            print("완료")
        else:
            print("실패 (fallback)")

    # 3. FAQ 섹션
    if faq:
        print("    [3] FAQ 섹션 생성 중...", end=" ", flush=True)
        faq_text = "\n".join(
            f"Q. {item.get('q', '')}\nA. {item.get('a', '')}"
            for item in faq[:5] if isinstance(item, dict)
        )
        img = generate_detail_section("faq", faq_text, product_name, style, height=500)
        if img:
            path = os.path.join(output_dir, "03_faq.png")
            _save_image(img, path)
            generated.append(path)
            print("완료")
        else:
            print("실패 (fallback)")

    # 4. CTA 배너
    print("    [4] CTA 배너 생성 중...", end=" ", flush=True)
    pricing = premium_result.get("pricing", {})
    price = pricing.get("final_price", 0)
    cta_text = f"지금 바로 시작하세요\n₩{int(price):,}" if price else "지금 바로 시작하세요"
    img = generate_detail_section("cta", cta_text, product_name, style, height=200)
    if img:
        path = os.path.join(output_dir, "04_cta.png")
        _save_image(img, path)
        generated.append(path)
        print("완료")
    else:
        print("실패 (fallback)")

    return generated


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gemini 이미지 생성/편집")
    sub = parser.add_subparsers(dest="command")

    # generate: 상세페이지 이미지 생성
    p_gen = sub.add_parser("generate", help="상세페이지 이미지 생성")
    p_gen.add_argument("json_file", help="premium 결과 JSON")
    p_gen.add_argument("--output", "-o", default="detail_images")
    p_gen.add_argument("--style", default="premium", choices=["premium", "clean", "warm", "minimal"])

    # translate: 이미지 번역
    p_trans = sub.add_parser("translate", help="이미지 내 텍스트 번역")
    p_trans.add_argument("image", help="이미지 파일")
    p_trans.add_argument("--product", default="", help="상품명")
    p_trans.add_argument("--output", "-o", default="translated.png")

    # redesign: 이미지 리디자인
    p_redesign = sub.add_parser("redesign", help="이미지 리디자인")
    p_redesign.add_argument("image", help="이미지 파일")
    p_redesign.add_argument("--instruction", "-i", required=True, help="리디자인 지시사항")
    p_redesign.add_argument("--output", "-o", default="redesigned.png")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
    elif args.command == "generate":
        with open(args.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        detail = data.get("results", {}).get("detail_page", data.get("detail_page", data))
        detail["pricing"] = data.get("results", {}).get("pricing", {})

        generated = generate_full_detail_page(detail, args.output, args.style)
        print(f"\n생성 완료: {len(generated)}장 → {args.output}/")

    elif args.command == "translate":
        img = Image.open(args.image)
        result = translate_image(img, product_name=args.product)
        if result:
            _save_image(result, args.output)
            print(f"번역 완료: {args.output}")
        else:
            print("번역 실패")

    elif args.command == "redesign":
        img = Image.open(args.image)
        result = redesign_product_image(img, args.instruction)
        if result:
            _save_image(result, args.output)
            print(f"리디자인 완료: {args.output}")
        else:
            print("리디자인 실패")
