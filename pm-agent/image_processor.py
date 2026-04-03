#!/usr/bin/env python3
"""
이미지 현지화 CLI
==================
타오바오/1688 상품 이미지를 한국 이커머스용으로 변환
(이미지 현지화 시스템 API 연동)

기능:
  - 중국어 텍스트 OCR → 한국어 번역
  - 리스크 이미지 감지 (유아/인물/로고)
  - 무드톤 보정 (premium/value/minimal/trendy)
  - SEO 메타데이터 생성

사용법:
  python image_processor.py image1.jpg image2.png
  python image_processor.py *.jpg --moodtone premium
  python image_processor.py product_images/ --output processed/

필수: 이미지 현지화 시스템이 실행 중이어야 함 (docker-compose up)
"""

import os
import sys
import glob
import argparse
import logging
import httpx
from pathlib import Path
from datetime import datetime

# .env 로드
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

API_BASE = os.getenv("IMAGE_API_URL", "http://localhost:8000")


def check_service():
    """이미지 현지화 서비스 상태 확인"""
    try:
        r = httpx.get(f"{API_BASE}/health", timeout=5)
        data = r.json()
        if data.get("status") == "healthy":
            return True
        print(f"  ⚠️  서비스 상태: {data}")
        return False
    except Exception as e:
        print(f"  ❌ 이미지 현지화 서비스에 연결할 수 없습니다 ({API_BASE})")
        print(f"     docker-compose up -d 로 서비스를 시작하세요")
        return False


def process_images(
    image_paths: list,
    moodtone: str = "premium",
    brand_type: str = "fortimove_global",
    product_name: str = "",
    output_dir: str = "processed_images",
):
    """이미지 현지화 API 호출"""

    os.makedirs(output_dir, exist_ok=True)

    files = []
    for path in image_paths:
        p = Path(path)
        if not p.exists():
            print(f"  ⚠️  파일 없음: {path}")
            continue
        if p.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            print(f"  ⚠️  지원하지 않는 형식: {path}")
            continue
        files.append(("files", (p.name, open(p, "rb"), f"image/{p.suffix.lstrip('.')}")))

    if not files:
        print("  ❌ 처리할 이미지가 없습니다")
        return None

    print(f"  📤 {len(files)}개 이미지 전송 중...")

    try:
        with httpx.Client(timeout=120) as client:
            r = client.post(
                f"{API_BASE}/api/v1/process",
                files=files,
                data={
                    "moodtone": moodtone,
                    "brand_type": brand_type,
                    "product_name": product_name or "",
                    "generate_seo": "true",
                    "auto_replace_risks": "true",
                },
            )
            r.raise_for_status()
            result = r.json()
    except httpx.HTTPStatusError as e:
        print(f"  ❌ API 오류: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"  ❌ 연결 오류: {e}")
        return None
    finally:
        for _, (_, f, _) in files:
            f.close()

    # 결과 처리
    status = result.get("status", "?")
    if status == "failed":
        print(f"  ❌ 처리 실패: {result.get('error_message', '?')}")
        return result

    processed = result.get("processed_images", [])
    analysis = result.get("analysis_report", {})
    seo = result.get("seo_metadata")
    time_sec = result.get("processing_time_seconds", 0)

    print(f"  ✅ 처리 완료 ({time_sec:.1f}초)")
    print()

    # OCR 결과
    ocr = analysis.get("ocr_results", [])
    if ocr:
        print(f"  ━━━ OCR 추출 텍스트 ({len(ocr)}건) ━━━")
        for item in ocr[:10]:
            text = item.get("text", "") if isinstance(item, dict) else str(item)
            print(f"    {text[:60]}")
        print()

    # 번역 결과
    translations = analysis.get("translations", [])
    if translations:
        print(f"  ━━━ 번역 ({len(translations)}건) ━━━")
        for item in translations[:10]:
            if isinstance(item, dict):
                orig = item.get("original", "")
                trans = item.get("translated", "")
                print(f"    {orig[:25]} → {trans[:25]}")
            else:
                print(f"    {str(item)[:50]}")
        print()

    # 리스크
    risks = analysis.get("risks_detected", [])
    if risks:
        print(f"  ━━━ 리스크 감지 ({len(risks)}건) ━━━")
        for risk in risks:
            if isinstance(risk, dict):
                print(f"    ⚠️  {risk.get('type', '?')}: {risk.get('description', '')[:50]}")
            else:
                print(f"    ⚠️  {str(risk)[:50]}")
        print()

    # 처리된 이미지 다운로드
    for img in processed:
        download_url = img.get("download_url", "")
        filename = img.get("processed_filename", "unknown.jpg")
        out_path = os.path.join(output_dir, filename)

        try:
            with httpx.Client(timeout=30) as client:
                dl = client.get(download_url)
                dl.raise_for_status()
                with open(out_path, "wb") as f:
                    f.write(dl.content)
            size_kb = os.path.getsize(out_path) / 1024
            print(f"  📥 {filename} ({size_kb:.0f}KB)")
        except Exception as e:
            print(f"  ⚠️  다운로드 실패: {filename} - {e}")

    # SEO 메타데이터
    if seo:
        print(f"\n  ━━━ SEO 메타데이터 ━━━")
        if isinstance(seo, dict):
            for k, v in seo.items():
                print(f"    {k}: {str(v)[:60]}")

    print(f"\n  📁 출력: {output_dir}/")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="이미지 현지화 — 중국어 이미지를 한국 이커머스용으로 변환",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 단일 이미지
  python image_processor.py product.jpg

  # 여러 이미지 + 프리미엄 무드톤
  python image_processor.py img1.jpg img2.png --moodtone premium

  # 폴더 내 전체 이미지
  python image_processor.py images/*.jpg --output processed/

  # 상품명 포함 (SEO 메타데이터에 반영)
  python image_processor.py *.jpg --product "콜라겐 분말"
        """
    )
    parser.add_argument("images", nargs="+", help="이미지 파일(들) 또는 glob 패턴")
    parser.add_argument("--moodtone", default="premium", choices=["premium", "value", "minimal", "trendy"])
    parser.add_argument("--brand", default="fortimove_global", help="브랜드 타입")
    parser.add_argument("--product", default="", help="상품명 (SEO용)")
    parser.add_argument("--output", "-o", default="processed_images", help="출력 디렉토리")
    args = parser.parse_args()

    # glob 패턴 확장
    all_paths = []
    for pattern in args.images:
        expanded = glob.glob(pattern)
        if expanded:
            all_paths.extend(expanded)
        else:
            all_paths.append(pattern)

    if not all_paths:
        print("❌ 이미지 파일이 없습니다")
        sys.exit(1)

    print(f"\n{'='*50}")
    print(f"  이미지 현지화 ({len(all_paths)}개)")
    print(f"  무드톤: {args.moodtone}")
    print(f"{'='*50}\n")

    if not check_service():
        sys.exit(1)

    process_images(
        image_paths=all_paths,
        moodtone=args.moodtone,
        brand_type=args.brand,
        product_name=args.product,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()
