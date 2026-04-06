"""
Detail Page Composer — 100% PIL 기반 상세페이지 이미지 엔진

5개 섹션 이미지 생성 (모두 PIL 렌더링):
  1. Hero 배너 (860 x 700)
  2. 혜택 패널 (860 x dynamic)
  3. 문제-해결 패널 (860 x dynamic)
  4. FAQ 패널 (860 x dynamic)
  5. 스펙/주의사항 패널 (860 x dynamic)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).parent / "fonts"
PAGE_WIDTH = 860
IMAGE_QUALITY = 92

# ── 무드톤 색상 프리셋 ─────────────────────────────────────

COLOR_PRESETS = {
    "premium": {
        "bg": (250, 249, 246),
        "primary": (26, 26, 26),
        "secondary": (107, 107, 107),
        "accent": (201, 169, 110),
        "card": (255, 255, 255),
        "divider": (232, 228, 223),
        "hero_bg": (42, 38, 34),
        "hero_text": (255, 255, 255),
        "hero_sub": (200, 200, 200),
        "problem_top": (245, 243, 240),
    },
    "value": {
        "bg": (255, 255, 255),
        "primary": (34, 34, 34),
        "secondary": (85, 85, 85),
        "accent": (255, 107, 53),
        "card": (255, 248, 244),
        "divider": (238, 238, 238),
        "hero_bg": (34, 34, 34),
        "hero_text": (255, 255, 255),
        "hero_sub": (210, 210, 210),
        "problem_top": (255, 248, 244),
    },
    "minimal": {
        "bg": (255, 255, 255),
        "primary": (51, 51, 51),
        "secondary": (136, 136, 136),
        "accent": (74, 144, 217),
        "card": (247, 249, 252),
        "divider": (229, 229, 229),
        "hero_bg": (30, 42, 56),
        "hero_text": (255, 255, 255),
        "hero_sub": (190, 205, 220),
        "problem_top": (247, 249, 252),
    },
    "trendy": {
        "bg": (245, 240, 235),
        "primary": (45, 45, 45),
        "secondary": (102, 102, 102),
        "accent": (232, 93, 117),
        "card": (255, 255, 255),
        "divider": (221, 216, 210),
        "hero_bg": (45, 40, 38),
        "hero_text": (255, 255, 255),
        "hero_sub": (210, 200, 195),
        "problem_top": (250, 245, 240),
    },
}


class DetailPageComposer:

    def __init__(self, moodtone: str = "premium"):
        self.moodtone = moodtone
        self.colors = COLOR_PRESETS.get(moodtone, COLOR_PRESETS["premium"])
        self.padding = 60

        # Typography hierarchy
        self.font_title = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Bold.ttf"), 40)
        self.font_subtitle = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Bold.ttf"), 28)
        self.font_body = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Regular.ttf"), 22)
        self.font_caption = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Regular.ttf"), 18)
        self.font_brand = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Bold.ttf"), 16)
        self.font_number = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Bold.ttf"), 36)

    # ── Text wrapping utility ────────────────────────────────

    def _wrap_text_words(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
        """Wrap text by words (split on spaces). Better for titles with mixed scripts."""
        words = text.split(' ')
        lines: List[str] = []
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > max_width and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)
        return lines if lines else [text]

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> List[str]:
        """Wrap text to fit within max_width, handling newlines."""
        lines: List[str] = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue
            current_line = ""
            for char in paragraph:
                test = current_line + char
                bbox = draw.textbbox((0, 0), test, font=font)
                if bbox[2] > max_width:
                    if current_line:
                        lines.append(current_line)
                    current_line = char
                else:
                    current_line = test
            if current_line:
                lines.append(current_line)
        return lines

    def _text_height(self, draw: ImageDraw.ImageDraw, text: str, font) -> int:
        """Get the height of a single line of text."""
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]

    def _draw_rounded_rect(
        self, draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width: int = 1
    ):
        """Draw a rounded rectangle. xy = (x0, y0, x1, y1)."""
        x0, y0, x1, y1 = xy
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

    # ── Section 1: Hero Banner (860 x 700) ───────────────────

    def _compose_hero(self, text_content: Dict, image_path: Optional[str], output_path: str) -> None:
        title = text_content.get("main_title", "Premium Product")
        hooks = text_content.get("hook_copies", [])
        hook = hooks[0] if hooks else ""

        width, height = PAGE_WIDTH, 700
        img = Image.new("RGB", (width, height), self.colors["hero_bg"])
        draw = ImageDraw.Draw(img)

        pad = self.padding
        text_area_width = 420 if image_path else (width - pad * 2)

        # Brand tag
        brand_y = pad + 40
        draw.text((pad, brand_y), "FORTIMOVE", font=self.font_brand, fill=self.colors["accent"])

        # Accent underline below brand
        brand_bbox = draw.textbbox((pad, brand_y), "FORTIMOVE", font=self.font_brand)
        draw.rectangle(
            [pad, brand_bbox[3] + 6, pad + 50, brand_bbox[3] + 9],
            fill=self.colors["accent"],
        )

        # Main title (word-based wrapping to avoid mid-word breaks)
        title_y = brand_bbox[3] + 30
        title_font = self.font_title
        title_lines = self._wrap_text_words(draw, title, title_font, text_area_width)
        # If title is too long (>3 lines), reduce font size
        if len(title_lines) > 3:
            title_font = ImageFont.truetype(str(FONTS_DIR / "NanumGothic-Bold.ttf"), 32)
            title_lines = self._wrap_text_words(draw, title, title_font, text_area_width)
        line_spacing = 52 if title_font == self.font_title else 42
        for line in title_lines:
            draw.text((pad, title_y), line, font=title_font, fill=self.colors["hero_text"])
            title_y += line_spacing

        # Hook copy
        if hook:
            hook_y = title_y + 24
            hook_lines = self._wrap_text(draw, hook, self.font_body, text_area_width)
            for line in hook_lines:
                draw.text((pad, hook_y), line, font=self.font_body, fill=self.colors["hero_sub"])
                hook_y += 30

        # Product image on right side
        if image_path and Path(image_path).exists():
            try:
                product_img = Image.open(image_path).convert("RGBA")
                max_w, max_h = 350, 500
                ratio = min(max_w / product_img.width, max_h / product_img.height)
                new_w = int(product_img.width * ratio)
                new_h = int(product_img.height * ratio)
                product_img = product_img.resize((new_w, new_h), Image.LANCZOS)

                # Center in right area
                right_center_x = width - pad - max_w // 2
                center_y = height // 2
                paste_x = right_center_x - new_w // 2
                paste_y = center_y - new_h // 2

                # Composite with alpha
                if product_img.mode == "RGBA":
                    img.paste(product_img, (paste_x, paste_y), product_img)
                else:
                    img.paste(product_img, (paste_x, paste_y))
            except Exception as e:
                logger.warning(f"  상품 이미지 로드 실패: {e}")

        img.save(output_path, "JPEG", quality=IMAGE_QUALITY)

    # ── Section 2: Benefits Panel (860 x dynamic) ────────────

    def _compose_benefits(self, text_content: Dict, output_path: str) -> None:
        benefits = text_content.get("key_benefits", ["프리미엄 품질", "빠른 배송", "전문가 검수"])[:5]
        pad = self.padding
        content_width = PAGE_WIDTH - pad * 2

        # Measure layout to determine image height
        dummy = Image.new("RGB", (1, 1))
        dd = ImageDraw.Draw(dummy)

        header_height = 110  # brand tag + title + spacing
        card_height = 80
        card_gap = 16
        total_cards_height = len(benefits) * card_height + (len(benefits) - 1) * card_gap
        total_height = pad + header_height + total_cards_height + pad

        img = Image.new("RGB", (PAGE_WIDTH, total_height), self.colors["bg"])
        draw = ImageDraw.Draw(img)

        y = pad

        # Section label
        draw.text((pad, y), "WHY FORTIMOVE", font=self.font_brand, fill=self.colors["accent"])
        y += 28

        # Section title
        draw.text((pad, y), "이 상품을 선택해야 하는 이유", font=self.font_title, fill=self.colors["primary"])
        y += 56

        # Divider
        draw.rectangle([pad, y, pad + 60, y + 3], fill=self.colors["accent"])
        y += 26

        # Benefit cards
        for i, benefit in enumerate(benefits):
            card_x0 = pad
            card_y0 = y
            card_x1 = PAGE_WIDTH - pad
            card_y1 = y + card_height

            # Card background
            self._draw_rounded_rect(draw, (card_x0, card_y0, card_x1, card_y1), radius=12, fill=self.colors["card"])
            # Subtle border
            self._draw_rounded_rect(
                draw, (card_x0, card_y0, card_x1, card_y1),
                radius=12, outline=self.colors["divider"], width=1,
            )

            # Number in accent color
            num_text = f"{i + 1:02d}"
            num_x = card_x0 + 24
            num_y = card_y0 + (card_height - 36) // 2 - 2
            draw.text((num_x, num_y), num_text, font=self.font_number, fill=self.colors["accent"])

            # Vertical separator
            sep_x = num_x + 64
            draw.rectangle([sep_x, card_y0 + 18, sep_x + 1, card_y1 - 18], fill=self.colors["divider"])

            # Benefit text
            text_x = sep_x + 24
            text_y = card_y0 + (card_height - 22) // 2 - 2
            benefit_lines = self._wrap_text(draw, benefit, self.font_body, card_x1 - text_x - 24)
            for bl in benefit_lines:
                draw.text((text_x, text_y), bl, font=self.font_body, fill=self.colors["primary"])
                text_y += 28

            y += card_height + card_gap

        img.save(output_path, "JPEG", quality=IMAGE_QUALITY)

    # ── Section 3: Problem-Solution (860 x dynamic) ──────────

    def _compose_problem_solution(self, text_content: Dict, output_path: str) -> None:
        scenarios = text_content.get("problem_scenarios", [])[:5]
        narrative = text_content.get("solution_narrative", "")
        pad = self.padding
        content_width = PAGE_WIDTH - pad * 2

        # Pre-measure
        dummy = Image.new("RGB", (1, 1))
        dd = ImageDraw.Draw(dummy)

        # Problem section height
        problem_header = 90
        problem_item_h = 36
        problem_section_h = pad + problem_header + len(scenarios) * problem_item_h + 30

        # Divider
        divider_h = 40

        # Solution section height
        solution_header = 60
        narrative_lines = self._wrap_text(dd, narrative, self.font_body, content_width - 20) if narrative else []
        solution_text_h = len(narrative_lines) * 30 + 20
        solution_section_h = solution_header + solution_text_h + pad

        total_height = problem_section_h + divider_h + solution_section_h

        img = Image.new("RGB", (PAGE_WIDTH, total_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # ── Problem area (lighter background) ──
        draw.rectangle([0, 0, PAGE_WIDTH, problem_section_h], fill=self.colors["problem_top"])

        y = pad

        # Label
        draw.text((pad, y), "SOLUTION", font=self.font_brand, fill=self.colors["accent"])
        y += 28

        # Title
        draw.text((pad, y), "이런 고민, 있으셨나요?", font=self.font_title, fill=self.colors["primary"])
        y += 56

        # Problem bullets
        for scenario in scenarios:
            bullet_text = f"•  {scenario}"
            lines = self._wrap_text(draw, bullet_text, self.font_body, content_width)
            for line in lines:
                draw.text((pad + 10, y), line, font=self.font_body, fill=self.colors["secondary"])
                y += problem_item_h

        # ── Divider ──
        divider_y = problem_section_h + divider_h // 2
        draw.line(
            [(pad, divider_y), (PAGE_WIDTH - pad, divider_y)],
            fill=self.colors["divider"], width=2,
        )

        # ── Solution area (white background) ──
        y = problem_section_h + divider_h

        # Arrow / indicator
        arrow_text = "▼  FORTIMOVE의 답"
        draw.text((pad, y), arrow_text, font=self.font_subtitle, fill=self.colors["accent"])
        y += 48

        # Solution card
        if narrative_lines:
            card_x0 = pad
            card_y0 = y
            card_text_h = len(narrative_lines) * 30 + 40
            card_y1 = card_y0 + card_text_h

            self._draw_rounded_rect(
                draw, (card_x0, card_y0, PAGE_WIDTH - pad, card_y1),
                radius=12, fill=self.colors["card"],
            )
            self._draw_rounded_rect(
                draw, (card_x0, card_y0, PAGE_WIDTH - pad, card_y1),
                radius=12, outline=self.colors["divider"], width=1,
            )

            # Accent left bar
            draw.rectangle([card_x0, card_y0 + 8, card_x0 + 4, card_y1 - 8], fill=self.colors["accent"])

            text_y = card_y0 + 20
            for line in narrative_lines:
                draw.text((card_x0 + 24, text_y), line, font=self.font_body, fill=self.colors["primary"])
                text_y += 30

        img.save(output_path, "JPEG", quality=IMAGE_QUALITY)

    # ── Section 4: FAQ (860 x dynamic) ───────────────────────

    def _compose_faq(self, text_content: Dict, output_path: str) -> None:
        faq_list = text_content.get("faq", [])
        if isinstance(faq_list, list) and faq_list and isinstance(faq_list[0], dict):
            faqs = faq_list[:6]
        else:
            faqs = [{"q": "배송 기간은?", "a": "주문 후 7-14일 내 도착합니다."}]

        pad = self.padding
        content_width = PAGE_WIDTH - pad * 2

        # Pre-measure height
        dummy = Image.new("RGB", (1, 1))
        dd = ImageDraw.Draw(dummy)

        header_h = 100
        items_h = 0
        for faq in faqs:
            q_lines = self._wrap_text(dd, f"Q. {faq.get('q', '')}", self.font_subtitle, content_width - 48)
            a_lines = self._wrap_text(dd, f"A. {faq.get('a', '')}", self.font_body, content_width - 48)
            item_h = len(q_lines) * 36 + len(a_lines) * 28 + 40  # card padding + gap
            items_h += item_h + 16  # card gap

        total_height = pad + header_h + items_h + pad

        img = Image.new("RGB", (PAGE_WIDTH, total_height), self.colors["bg"])
        draw = ImageDraw.Draw(img)

        y = pad

        # Header
        draw.text((pad, y), "FAQ", font=self.font_brand, fill=self.colors["accent"])
        y += 28
        draw.text((pad, y), "자주 묻는 질문", font=self.font_title, fill=self.colors["primary"])
        y += 56
        draw.rectangle([pad, y, pad + 60, y + 3], fill=self.colors["accent"])
        y += 20

        # FAQ items as cards
        for faq in faqs:
            q_text = f"Q. {faq.get('q', '')}"
            a_text = f"A. {faq.get('a', '')}"

            q_lines = self._wrap_text(draw, q_text, self.font_subtitle, content_width - 48)
            a_lines = self._wrap_text(draw, a_text, self.font_body, content_width - 48)

            card_text_h = len(q_lines) * 36 + 12 + len(a_lines) * 28
            card_h = card_text_h + 40  # top/bottom padding

            # Card background
            self._draw_rounded_rect(
                draw, (pad, y, PAGE_WIDTH - pad, y + card_h),
                radius=12, fill=self.colors["card"],
            )
            self._draw_rounded_rect(
                draw, (pad, y, PAGE_WIDTH - pad, y + card_h),
                radius=12, outline=self.colors["divider"], width=1,
            )

            text_y = y + 20

            # Question
            for ql in q_lines:
                draw.text((pad + 24, text_y), ql, font=self.font_subtitle, fill=self.colors["primary"])
                text_y += 36

            text_y += 4

            # Answer
            for al in a_lines:
                draw.text((pad + 24, text_y), al, font=self.font_body, fill=self.colors["secondary"])
                text_y += 28

            y += card_h + 16

        # Crop to actual content
        final_h = y + pad
        img = img.crop((0, 0, PAGE_WIDTH, final_h))
        img.save(output_path, "JPEG", quality=IMAGE_QUALITY)

    # ── Section 5: Spec / Cautions (860 x dynamic) ───────────

    def _compose_spec(self, text_content: Dict, output_path: str) -> None:
        usage = text_content.get("usage_guide", "")
        cautions = text_content.get("cautions", "해외 구매대행 상품입니다.")

        notice = (
            "[해외구매대행 필수 고지사항]\n"
            "• 본 상품은 해외 구매대행 상품으로, 국내 A/S가 제한될 수 있습니다.\n"
            "• 통관 과정에서 관부가세가 부과될 수 있습니다.\n"
            "• 교환/반품 시 국제 배송비가 발생합니다.\n"
            "• 상품 수령 후 7일 이내 교환/반품 접수 가능합니다."
        )

        pad = self.padding
        content_width = PAGE_WIDTH - pad * 2

        # Build content blocks: list of (label, text) tuples
        blocks: List[tuple] = []
        if usage:
            blocks.append(("사용 가이드", usage))
        if cautions:
            blocks.append(("주의사항", cautions))
        blocks.append(("해외구매대행 필수 고지사항", notice.split("\n", 1)[1]))

        # Pre-measure height
        dummy = Image.new("RGB", (1, 1))
        dd = ImageDraw.Draw(dummy)

        header_h = 80
        block_heights = []
        for label, body in blocks:
            body_lines = self._wrap_text(dd, body, self.font_caption, content_width - 40)
            bh = 36 + len(body_lines) * 24 + 30  # label + lines + gap
            block_heights.append(bh)

        total_height = pad + header_h + sum(block_heights) + pad

        img = Image.new("RGB", (PAGE_WIDTH, total_height), self.colors["card"])
        draw = ImageDraw.Draw(img)

        y = pad

        # Header
        draw.text((pad, y), "상품 정보 및 주의사항", font=self.font_subtitle, fill=self.colors["primary"])
        y += 40
        draw.line([(pad, y), (PAGE_WIDTH - pad, y)], fill=self.colors["divider"], width=1)
        y += 24

        # Content blocks
        for i, (label, body) in enumerate(blocks):
            # Label in accent
            draw.text((pad, y), f"[ {label} ]", font=self.font_caption, fill=self.colors["accent"])
            y += 30

            # Body text
            body_lines = self._wrap_text(draw, body, self.font_caption, content_width - 20)
            for line in body_lines:
                draw.text((pad + 10, y), line, font=self.font_caption, fill=self.colors["secondary"])
                y += 24

            # Divider between blocks
            if i < len(blocks) - 1:
                y += 12
                draw.line([(pad, y), (PAGE_WIDTH - pad, y)], fill=self.colors["divider"], width=1)
                y += 16

        final_h = y + pad
        img = img.crop((0, 0, PAGE_WIDTH, final_h))
        img.save(output_path, "JPEG", quality=IMAGE_QUALITY)

    # ── Main composition ─────────────────────────────────────

    def compose_detail_page(
        self,
        text_content: Dict[str, Any],
        image_paths: List[str],
        output_dir: str,
    ) -> List[Dict[str, Any]]:
        """전체 상세페이지 합성 (5개 섹션) -> 이미지 파일 저장"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        hero_image = image_paths[0] if image_paths else None
        results: List[Dict[str, Any]] = []

        sections = [
            ("hero", lambda p: self._compose_hero(text_content, hero_image, p)),
            ("benefits", lambda p: self._compose_benefits(text_content, p)),
            ("problem_solution", lambda p: self._compose_problem_solution(text_content, p)),
            ("faq", lambda p: self._compose_faq(text_content, p)),
            ("spec", lambda p: self._compose_spec(text_content, p)),
        ]

        for order, (section_type, render_fn) in enumerate(sections):
            filename = f"{order + 1:02d}_{section_type}.jpg"
            filepath = str(out / filename)

            try:
                render_fn(filepath)
                img = Image.open(filepath)
                results.append({
                    "filename": filename,
                    "section_type": section_type,
                    "display_order": order + 1,
                    "width": img.width,
                    "height": img.height,
                    "engine": "pil",
                })
                logger.info(f"  합성 완료: {filename} ({img.width}x{img.height})")
            except Exception as e:
                logger.error(f"  섹션 렌더링 실패 [{section_type}]: {e}")
                raise

        return results

    def compose_single_section(
        self,
        section_type: str,
        text_content: Dict[str, Any],
        image_path: Optional[str],
        output_dir: str,
    ) -> Dict[str, Any]:
        """단일 섹션 재합성"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        section_order = {"hero": 1, "benefits": 2, "problem_solution": 3, "faq": 4, "spec": 5}
        order = section_order.get(section_type, 1)
        filename = f"{order:02d}_{section_type}.jpg"
        filepath = str(out / filename)

        render_map = {
            "hero": lambda: self._compose_hero(text_content, image_path, filepath),
            "benefits": lambda: self._compose_benefits(text_content, filepath),
            "problem_solution": lambda: self._compose_problem_solution(text_content, filepath),
            "faq": lambda: self._compose_faq(text_content, filepath),
            "spec": lambda: self._compose_spec(text_content, filepath),
        }

        render_fn = render_map.get(section_type)
        if render_fn is None:
            raise ValueError(f"Unknown section_type: {section_type}")

        render_fn()

        img = Image.open(filepath)
        return {
            "filename": filename,
            "section_type": section_type,
            "display_order": order,
            "width": img.width,
            "height": img.height,
            "engine": "pil",
        }


if __name__ == "__main__":
    import tempfile

    composer = DetailPageComposer(moodtone="premium")

    test_content = {
        "main_title": "프리미엄 비타민 C 1000mg",
        "hook_copies": ["매일 아침, 활력이 부족하다고 느끼셨나요?"],
        "key_benefits": [
            "영국 직수입 프리미엄 원료 사용",
            "1일 1정으로 간편한 섭취",
            "전문 약사 검수 완료 상품",
            "GMP 인증 시설에서 생산",
        ],
        "problem_scenarios": [
            "아침에 일어나기 힘들고 무기력한 날이 반복된다",
            "환절기만 되면 컨디션이 떨어진다",
            "비타민 제품이 너무 많아 뭘 골라야 할지 모르겠다",
        ],
        "solution_narrative": "Fortimove가 엄선한 프리미엄 비타민 C는 영국에서 직수입한 고품질 원료를 사용합니다.",
        "faq": [
            {"q": "하루에 몇 알 먹나요?", "a": "1일 1회, 1정을 물과 함께 섭취하세요."},
            {"q": "배송은 얼마나 걸리나요?", "a": "주문 후 7-14 영업일 내 도착합니다."},
            {"q": "교환/반품이 가능한가요?", "a": "수령 후 7일 이내 접수 가능하며, 국제 배송비가 발생합니다."},
        ],
        "usage_guide": "1일 1회, 1정을 물과 함께 섭취하세요.",
        "cautions": "임산부, 수유부는 섭취 전 전문가와 상담하세요.",
    }

    output_dir = tempfile.mkdtemp(prefix="detail_page_pil_")
    print(f"출력 디렉토리: {output_dir}\n")

    results = composer.compose_detail_page(test_content, [], output_dir)

    for r in results:
        print(f"  {r['filename']} -- {r['width']}x{r['height']} [{r['engine']}]")
