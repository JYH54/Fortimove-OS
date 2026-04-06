#!/usr/bin/env python3
"""
상세페이지 이미지 생성기
=========================
premium_detail_page 결과를 실제 상세페이지 이미지(PNG)로 변환

셀러들이 피그마로 만드는 수준의 비주얼 상세페이지를 자동 생성:
  - 히어로 배너 (후크 카피 + 그라데이션 배경)
  - 혜택 카드 (아이콘 + 텍스트)
  - 문제-해결 섹션
  - 스펙/성분 테이블
  - FAQ 섹션
  - 구매 CTA

출력: 섹션별 이미지 파일 (860px 너비, 스마트스토어 최적)

사용법:
  python detail_image_generator.py reports/premium_20260403.json
  python detail_image_generator.py reports/premium_*.json --output detail_images/
  python fortimove.py detail-img reports/premium_20260403.json
"""

import os
import sys
import json
import glob
import argparse
import textwrap
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 이미지 설정
WIDTH = 860
SECTION_PADDING = 40
LINE_SPACING = 1.6

# 색상 팔레트
COLORS = {
    "primary": (108, 92, 231),       # 보라
    "primary_dark": (87, 75, 185),
    "secondary": (0, 206, 201),      # 민트
    "accent": (255, 107, 53),        # 오렌지
    "white": (255, 255, 255),
    "black": (45, 52, 54),
    "gray_dark": (99, 110, 114),
    "gray_light": (178, 190, 195),
    "gray_bg": (245, 246, 250),
    "warm_bg": (255, 248, 240),
    "success": (0, 184, 148),
    "warning": (253, 203, 110),
}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """한국어 폰트 로드"""
    font_paths = [
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "static/fonts/NotoSansKR-Bold.otf" if bold else "static/fonts/NotoSansKR-Regular.otf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """텍스트를 이미지 너비에 맞게 줄바꿈"""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        # 한글은 글자 단위로 자름
        current = ""
        for char in paragraph:
            test = current + char
            bbox = font.getbbox(test)
            if bbox[2] > max_width:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
    return lines


def _draw_gradient_rect(draw: ImageDraw.Draw, xy: Tuple, color1: Tuple, color2: Tuple, direction: str = "horizontal"):
    """그라데이션 사각형"""
    x1, y1, x2, y2 = xy
    if direction == "vertical":
        for y in range(y1, y2):
            ratio = (y - y1) / max(1, y2 - y1)
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            draw.line([(x1, y), (x2, y)], fill=(r, g, b))
    else:
        for x in range(x1, x2):
            ratio = (x - x1) / max(1, x2 - x1)
            r = int(color1[0] + (color2[0] - color1[0]) * ratio)
            g = int(color1[1] + (color2[1] - color1[1]) * ratio)
            b = int(color1[2] + (color2[2] - color1[2]) * ratio)
            draw.line([(x, y1), (x, y2)], fill=(r, g, b))


def _draw_rounded_rect(draw: ImageDraw.Draw, xy: Tuple, fill: Tuple, radius: int = 12):
    """둥근 모서리 사각형"""
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def generate_hero_banner(hooks: List[str], product_title: str = "") -> Image.Image:
    """히어로 배너 — 후크 카피 + 그라데이션 배경"""
    height = 400
    img = Image.new("RGB", (WIDTH, height), COLORS["white"])
    draw = ImageDraw.Draw(img)

    # 그라데이션 배경
    _draw_gradient_rect(draw, (0, 0, WIDTH, height), (108, 92, 231), (118, 75, 162), "vertical")

    # 후크 카피
    y = 80
    for i, hook in enumerate(hooks[:3]):
        font_size = 32 if i == 0 else 24
        font = _get_font(font_size, bold=(i == 0))
        lines = _wrap_text(hook, font, WIDTH - 120)
        for line in lines:
            bbox = font.getbbox(line)
            x = (WIDTH - bbox[2]) // 2
            draw.text((x, y), line, font=font, fill=COLORS["white"])
            y += int(font_size * LINE_SPACING)
        y += 15

    # 하단 구분선
    draw.line([(WIDTH // 4, height - 30), (WIDTH * 3 // 4, height - 30)], fill=(255, 255, 255, 128), width=2)

    return img


def generate_benefits_section(benefits: List[str], title: str = "이런 점이 좋습니다") -> Image.Image:
    """혜택 카드 섹션"""
    card_height = 70
    padding = SECTION_PADDING
    total_height = padding + 60 + len(benefits) * card_height + padding

    img = Image.new("RGB", (WIDTH, total_height), COLORS["white"])
    draw = ImageDraw.Draw(img)

    # 섹션 제목
    title_font = _get_font(22, bold=True)
    draw.text((padding, padding), title, font=title_font, fill=COLORS["primary"])
    draw.line([(padding, padding + 35), (padding + 200, padding + 35)], fill=COLORS["primary"], width=3)

    y = padding + 60
    body_font = _get_font(16)
    check_font = _get_font(18, bold=True)

    for i, benefit in enumerate(benefits):
        # 카드 배경 (교차)
        bg = COLORS["gray_bg"] if i % 2 == 0 else COLORS["white"]
        _draw_rounded_rect(draw, (padding, y, WIDTH - padding, y + card_height - 8), fill=bg, radius=8)

        # 체크 아이콘
        draw.text((padding + 15, y + 18), "✓", font=check_font, fill=COLORS["success"])

        # 텍스트
        lines = _wrap_text(benefit, body_font, WIDTH - padding * 2 - 60)
        text_y = y + 20
        for line in lines:
            draw.text((padding + 45, text_y), line, font=body_font, fill=COLORS["black"])
            text_y += 22

        y += card_height

    return img


def generate_problem_solution(problems: List[str], solution: str) -> Image.Image:
    """문제-해결 섹션"""
    padding = SECTION_PADDING
    body_font = _get_font(15)
    bold_font = _get_font(16, bold=True)

    # 높이 계산
    solution_lines = _wrap_text(solution, body_font, WIDTH - padding * 2 - 30)
    height = padding + 50 + len(problems) * 55 + 40 + len(solution_lines) * 24 + padding + 40

    img = Image.new("RGB", (WIDTH, height), COLORS["warm_bg"])
    draw = ImageDraw.Draw(img)

    # 제목
    title_font = _get_font(22, bold=True)
    draw.text((padding, padding), "이런 분들께 추천합니다", font=title_font, fill=COLORS["accent"])
    draw.line([(padding, padding + 35), (padding + 250, padding + 35)], fill=COLORS["accent"], width=3)

    # 문제 시나리오
    y = padding + 60
    for problem in problems:
        draw.text((padding + 15, y + 10), "▸", font=bold_font, fill=COLORS["accent"])
        lines = _wrap_text(problem, body_font, WIDTH - padding * 2 - 50)
        for line in lines:
            draw.text((padding + 40, y + 12), line, font=body_font, fill=COLORS["gray_dark"])
            y += 22
        y += 20

    # 구분선
    y += 10
    draw.line([(padding + 50, y), (WIDTH - padding - 50, y)], fill=COLORS["gray_light"], width=1)
    y += 20

    # 해결 서사
    for line in solution_lines:
        draw.text((padding + 15, y), line, font=body_font, fill=COLORS["black"])
        y += 24

    return img


def generate_faq_section(faq: List[Dict]) -> Image.Image:
    """FAQ 섹션"""
    padding = SECTION_PADDING
    q_font = _get_font(15, bold=True)
    a_font = _get_font(14)

    # 높이 계산
    item_height = 90
    height = padding + 50 + len(faq) * item_height + padding

    img = Image.new("RGB", (WIDTH, height), COLORS["white"])
    draw = ImageDraw.Draw(img)

    title_font = _get_font(22, bold=True)
    draw.text((padding, padding), "자주 묻는 질문", font=title_font, fill=COLORS["primary"])
    draw.line([(padding, padding + 35), (padding + 180, padding + 35)], fill=COLORS["primary"], width=3)

    y = padding + 60
    for item in faq:
        q = item.get("q", "") if isinstance(item, dict) else ""
        a = item.get("a", "") if isinstance(item, dict) else ""

        # Q 배경
        _draw_rounded_rect(draw, (padding, y, WIDTH - padding, y + item_height - 10), fill=COLORS["gray_bg"], radius=8)

        # Q
        draw.text((padding + 15, y + 10), f"Q. {q}", font=q_font, fill=COLORS["black"])

        # A
        a_lines = _wrap_text(a, a_font, WIDTH - padding * 2 - 40)
        ay = y + 38
        for line in a_lines[:2]:
            draw.text((padding + 20, ay), line, font=a_font, fill=COLORS["gray_dark"])
            ay += 20

        y += item_height

    return img


def generate_cta_banner(price_krw: int = 0) -> Image.Image:
    """구매 CTA 배너"""
    height = 200
    img = Image.new("RGB", (WIDTH, height), COLORS["white"])
    draw = ImageDraw.Draw(img)

    _draw_gradient_rect(draw, (0, 0, WIDTH, height), COLORS["accent"], (255, 140, 90), "horizontal")

    # 메인 텍스트
    font_big = _get_font(28, bold=True)
    font_sub = _get_font(16)

    text1 = "지금 바로 시작하세요"
    bbox = font_big.getbbox(text1)
    draw.text(((WIDTH - bbox[2]) // 2, 50), text1, font=font_big, fill=COLORS["white"])

    if price_krw:
        price_text = f"₩{price_krw:,}"
        bbox2 = font_big.getbbox(price_text)
        draw.text(((WIDTH - bbox2[2]) // 2, 95), price_text, font=font_big, fill=COLORS["white"])

    # 하단 안내
    notice = "※ 본 제품은 질병의 예방 및 치료를 위한 의약품이 아닙니다."
    notice_font = _get_font(11)
    bbox3 = notice_font.getbbox(notice)
    draw.text(((WIDTH - bbox3[2]) // 2, height - 35), notice, font=notice_font, fill=(255, 255, 255, 180))

    return img


def generate_origin_trust(country_name: str, trust_label: str) -> Image.Image:
    """원산지 신뢰 배너"""
    height = 120
    img = Image.new("RGB", (WIDTH, height), COLORS["gray_bg"])
    draw = ImageDraw.Draw(img)

    font = _get_font(16, bold=True)
    sub_font = _get_font(13)

    draw.text((SECTION_PADDING, 25), f"🌍 {trust_label}", font=font, fill=COLORS["black"])
    draw.text((SECTION_PADDING, 60), "Fortimove가 직접 검수한 프리미엄 제품입니다", font=sub_font, fill=COLORS["gray_dark"])
    draw.text((SECTION_PADDING, 85), "품질 보증 | 안전 검수 | 빠른 배송", font=sub_font, fill=COLORS["gray_dark"])

    return img


def generate_detail_page_images(premium_result: Dict, output_dir: str = "detail_images") -> List[str]:
    """
    premium_detail_page 결과를 섹션별 이미지로 생성

    Returns: 생성된 이미지 파일 경로 리스트
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []

    hooks = premium_result.get("hook_copies", [])
    sections = premium_result.get("naver_detail_page", {}).get("sections", [])
    faq = premium_result.get("faq", [])
    titles = premium_result.get("product_titles", {})
    edge = premium_result.get("competitive_edge", {})

    # 1. 히어로 배너
    if hooks:
        img = generate_hero_banner(hooks, titles.get("smartstore", ""))
        path = os.path.join(output_dir, "01_hero_banner.png")
        img.save(path, "PNG", quality=95)
        generated.append(path)

    # 2. 혜택 섹션 — sections에서 추출
    benefits = []
    problems = []
    solution = ""
    for section in sections:
        content = section.get("content", "")
        name = section.get("section_name", "").lower()
        if "혜택" in name or "좋습니다" in name or "benefit" in name.lower():
            for line in content.split("\n"):
                line = line.strip().lstrip("✓•-· ")
                if line and len(line) > 5:
                    benefits.append(line)
        elif "추천" in name or "문제" in name or "이런 분" in name:
            for line in content.split("\n"):
                line = line.strip().lstrip("▸•-· ")
                if line and len(line) > 5:
                    problems.append(line)
        elif "스토리" in name or "소개" in name or "제품" in name:
            solution = content

    if benefits:
        img = generate_benefits_section(benefits[:7])
        path = os.path.join(output_dir, "02_benefits.png")
        img.save(path, "PNG", quality=95)
        generated.append(path)

    # 3. 문제-해결
    if problems and solution:
        img = generate_problem_solution(problems[:5], solution[:300])
        path = os.path.join(output_dir, "03_problem_solution.png")
        img.save(path, "PNG", quality=95)
        generated.append(path)

    # 4. FAQ
    if faq:
        img = generate_faq_section(faq[:5])
        path = os.path.join(output_dir, "04_faq.png")
        img.save(path, "PNG", quality=95)
        generated.append(path)

    # 5. 원산지 신뢰
    trust_label = ""
    for section in sections:
        if "원산지" in section.get("section_name", "") or "신뢰" in section.get("content", ""):
            trust_label = section.get("content", "")[:60]
            break
    if not trust_label:
        trust_label = premium_result.get("extracted_info", {}).get("origin_trust_label", "Fortimove 품질 검수 완료")

    img = generate_origin_trust("", trust_label)
    path = os.path.join(output_dir, "05_origin_trust.png")
    img.save(path, "PNG", quality=95)
    generated.append(path)

    # 6. CTA 배너
    price = 0
    pricing = premium_result.get("pricing", {})
    if pricing:
        price = int(pricing.get("final_price", 0))
    img = generate_cta_banner(price)
    path = os.path.join(output_dir, "06_cta.png")
    img.save(path, "PNG", quality=95)
    generated.append(path)

    return generated


def main():
    parser = argparse.ArgumentParser(description="상세페이지 이미지 생성")
    parser.add_argument("input_files", nargs="+", help="premium 결과 JSON 파일")
    parser.add_argument("--output", "-o", default="detail_images", help="출력 디렉토리")
    args = parser.parse_args()

    files = []
    for pattern in args.input_files:
        files.extend(glob.glob(pattern))

    if not files:
        print("파일을 찾을 수 없습니다")
        sys.exit(1)

    for filepath in files:
        print(f"\n처리: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # premium JSON 구조 감지
        detail = data.get("results", {}).get("detail_page", data.get("detail_page", data))

        if "error" in detail:
            print(f"  오류: {detail['error']}")
            continue

        # 출력 디렉토리
        base_name = Path(filepath).stem
        output_dir = os.path.join(args.output, base_name)

        generated = generate_detail_page_images(detail, output_dir)

        print(f"  생성 완료: {len(generated)}장")
        for path in generated:
            size = os.path.getsize(path)
            print(f"    {os.path.basename(path)} ({size//1024}KB)")

        print(f"  출력: {output_dir}/")


if __name__ == "__main__":
    main()
