#!/usr/bin/env python3
"""
이미지 번역 + 리디자인
=======================
기존 상품 이미지를 한국 이커머스에 맞게 번역 + 리디자인

기존 image_processor.py(API 래퍼)와 다르게, 이 도구는 로컬에서 직접 처리:
  - OCR (easyocr) → 중국어 텍스트 추출
  - Claude 번역 → 한국어 변환
  - 텍스트 영역 제거 + 한국어 텍스트 오버레이
  - 배경 제거 (rembg)
  - 톤 보정 (Pillow)
  - 깨끗한 한국어 상품 이미지로 재생성

사용법:
  python image_redesign.py product.jpg
  python image_redesign.py *.jpg --remove-bg --tone premium
  python image_redesign.py image.png --translate --output redesigned/
"""

import os
import sys
import glob
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


class ImageRedesigner:
    """이미지 번역 + 리디자인 엔진"""

    TONE_PRESETS = {
        "premium": {"saturation": 0.7, "brightness": 1.15, "contrast": 1.1, "sharpness": 1.2},
        "clean": {"saturation": 0.85, "brightness": 1.1, "contrast": 1.05, "sharpness": 1.1},
        "warm": {"saturation": 1.1, "brightness": 1.05, "contrast": 1.0, "sharpness": 1.0},
        "minimal": {"saturation": 0.5, "brightness": 1.1, "contrast": 1.15, "sharpness": 1.0},
    }

    def __init__(self):
        self.ocr_reader = None
        self.translator = None

    def _init_ocr(self):
        """EasyOCR 초기화 (lazy)"""
        if self.ocr_reader:
            return
        try:
            import easyocr
            self.ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            logger.info("EasyOCR 초기화 완료")
        except ImportError:
            logger.warning("easyocr 미설치 — pip install easyocr")

    def _init_translator(self):
        """Claude 번역 클라이언트 초기화 (lazy)"""
        if self.translator:
            return
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            from anthropic import Anthropic
            self.translator = Anthropic(api_key=api_key)

    def extract_text(self, image_path: str) -> List[Dict]:
        """이미지에서 텍스트 영역 추출 (위치 + 텍스트)"""
        self._init_ocr()
        if not self.ocr_reader:
            return []

        results = self.ocr_reader.readtext(image_path)
        texts = []
        for bbox, text, conf in results:
            if conf < 0.3:
                continue
            # bbox: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            texts.append({
                "text": text,
                "confidence": conf,
                "bbox": (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))),
            })
        return texts

    def translate_texts(self, texts: List[Dict]) -> List[Dict]:
        """추출된 텍스트를 한국어로 번역"""
        self._init_translator()
        if not self.translator or not texts:
            return texts

        # 전체 텍스트를 한 번에 번역 (API 호출 최소화)
        originals = [t["text"] for t in texts]
        joined = "\n".join(f"{i+1}. {t}" for i, t in enumerate(originals))

        try:
            response = self.translator.messages.create(
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": f"""다음 중국어/영어 텍스트를 한국어로 번역하세요.
상품 이미지에 들어갈 텍스트이므로 간결하고 자연스럽게.
번호 형식 그대로 유지.

{joined}

번역 결과만 출력 (번호. 한국어):"""
                }]
            )

            translated_text = response.content[0].text
            lines = translated_text.strip().split("\n")
            for i, line in enumerate(lines):
                if i < len(texts):
                    # "1. 번역문" 형태에서 번역문 추출
                    parts = line.split(".", 1)
                    if len(parts) == 2:
                        texts[i]["translated"] = parts[1].strip()
                    else:
                        texts[i]["translated"] = line.strip()

        except Exception as e:
            logger.error(f"번역 실패: {e}")
            for t in texts:
                t["translated"] = t["text"]

        return texts

    def replace_text_on_image(self, image: Image.Image, texts: List[Dict]) -> Image.Image:
        """이미지 위의 텍스트를 한국어로 교체"""
        draw = ImageDraw.Draw(image)

        for t in texts:
            translated = t.get("translated", t["text"])
            bbox = t["bbox"]  # (x1, y1, x2, y2)

            # 원본 텍스트 영역을 흰색으로 덮기
            padding = 3
            draw.rectangle(
                [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
                fill=(255, 255, 255)
            )

            # 한국어 텍스트 삽입
            text_height = bbox[3] - bbox[1]
            font_size = max(12, min(text_height - 2, 32))

            font_paths = [
                "C:/Windows/Fonts/malgunbd.ttf",
                "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            ]
            font = ImageFont.load_default()
            for fp in font_paths:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, font_size)
                    break

            draw.text((bbox[0] + 2, bbox[1] + 2), translated, font=font, fill=(33, 33, 33))

        return image

    def apply_tone(self, image: Image.Image, tone: str = "premium") -> Image.Image:
        """톤 보정 적용"""
        preset = self.TONE_PRESETS.get(tone, self.TONE_PRESETS["premium"])

        if preset["saturation"] != 1.0:
            image = ImageEnhance.Color(image).enhance(preset["saturation"])
        if preset["brightness"] != 1.0:
            image = ImageEnhance.Brightness(image).enhance(preset["brightness"])
        if preset["contrast"] != 1.0:
            image = ImageEnhance.Contrast(image).enhance(preset["contrast"])
        if preset["sharpness"] != 1.0:
            image = ImageEnhance.Sharpness(image).enhance(preset["sharpness"])

        return image

    def remove_background(self, image: Image.Image) -> Image.Image:
        """배경 제거 (rembg)"""
        try:
            from rembg import remove
            import io
            # PIL → bytes → rembg → PIL
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            result = remove(buf.getvalue())
            return Image.open(io.BytesIO(result)).convert("RGBA")
        except ImportError:
            logger.warning("rembg 미설치 — pip install rembg")
            return image
        except Exception as e:
            logger.error(f"배경 제거 실패: {e}")
            return image

    def redesign(
        self,
        image_path: str,
        translate: bool = True,
        remove_bg: bool = False,
        tone: str = "premium",
        resize_width: int = 860,
    ) -> Tuple[Image.Image, Dict]:
        """이미지 번역 + 리디자인 전체 파이프라인"""
        info = {"original": image_path, "operations": []}

        image = Image.open(image_path).convert("RGB")
        info["original_size"] = image.size

        # 1. 리사이즈
        if resize_width and image.width != resize_width:
            ratio = resize_width / image.width
            new_h = int(image.height * ratio)
            image = image.resize((resize_width, new_h), Image.LANCZOS)
            info["operations"].append(f"resize: {resize_width}x{new_h}")

        # 2. OCR + 번역 + 텍스트 교체
        if translate:
            texts = self.extract_text(image_path)
            info["ocr_count"] = len(texts)

            if texts:
                texts = self.translate_texts(texts)
                image = self.replace_text_on_image(image, texts)
                info["operations"].append(f"translate: {len(texts)} texts")
                info["translations"] = [
                    {"original": t["text"], "translated": t.get("translated", "")}
                    for t in texts
                ]

        # 3. 배경 제거
        if remove_bg:
            image = self.remove_background(image)
            info["operations"].append("remove_background")

        # 4. 톤 보정
        if tone:
            image = self.apply_tone(image, tone)
            info["operations"].append(f"tone: {tone}")

        return image, info


def main():
    parser = argparse.ArgumentParser(description="이미지 번역 + 리디자인")
    parser.add_argument("images", nargs="+", help="이미지 파일")
    parser.add_argument("--translate", action="store_true", default=True, help="텍스트 번역 (기본: 활성)")
    parser.add_argument("--no-translate", action="store_true", help="번역 비활성화")
    parser.add_argument("--remove-bg", action="store_true", help="배경 제거")
    parser.add_argument("--tone", default="premium", choices=["premium", "clean", "warm", "minimal"])
    parser.add_argument("--width", type=int, default=860, help="출력 너비 (기본: 860)")
    parser.add_argument("--output", "-o", default="redesigned", help="출력 디렉토리")
    args = parser.parse_args()

    files = []
    for pattern in args.images:
        files.extend(glob.glob(pattern))

    if not files:
        print("이미지 파일을 찾을 수 없습니다")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)
    redesigner = ImageRedesigner()

    print(f"\n{'='*50}")
    print(f"  이미지 리디자인 ({len(files)}장)")
    print(f"  번역: {'O' if not args.no_translate else 'X'} | 배경제거: {'O' if args.remove_bg else 'X'} | 톤: {args.tone}")
    print(f"{'='*50}\n")

    for filepath in files:
        print(f"  처리: {os.path.basename(filepath)}...", end=" ", flush=True)

        try:
            image, info = redesigner.redesign(
                filepath,
                translate=not args.no_translate,
                remove_bg=args.remove_bg,
                tone=args.tone,
                resize_width=args.width,
            )

            # 저장
            out_name = f"redesigned_{Path(filepath).stem}.png"
            out_path = os.path.join(args.output, out_name)

            if image.mode == "RGBA":
                image.save(out_path, "PNG")
            else:
                image.save(out_path, "PNG", quality=95)

            ocr_count = info.get("ocr_count", 0)
            size_kb = os.path.getsize(out_path) // 1024
            print(f"완료 (OCR:{ocr_count}건, {size_kb}KB)")

        except Exception as e:
            print(f"오류: {e}")

    print(f"\n  출력: {args.output}/")


if __name__ == "__main__":
    main()
