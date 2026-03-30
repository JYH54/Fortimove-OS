#!/usr/bin/env python3
"""
이미지 현지화 API 테스트 클라이언트
"""
import requests
import sys
import json
from pathlib import Path


def test_health():
    """헬스체크 테스트"""
    print("🔍 헬스체크 테스트...")

    try:
        response = requests.get("http://localhost:8000/health")
        response.raise_for_status()

        data = response.json()
        print(f"   ✅ 상태: {data['status']}")
        print(f"   버전: {data['version']}")
        print(f"   서비스:")
        for service, status in data['services'].items():
            print(f"      - {service}: {status}")
        return True

    except Exception as e:
        print(f"   ❌ 헬스체크 실패: {str(e)}")
        return False


def process_image(image_path: str):
    """이미지 처리 테스트"""
    print(f"\n📸 이미지 처리 테스트: {image_path}")

    if not Path(image_path).exists():
        print(f"   ❌ 파일 없음: {image_path}")
        return False

    try:
        # API 요청
        url = "http://localhost:8000/api/v1/process"

        files = {'files': open(image_path, 'rb')}
        data = {
            'moodtone': 'premium',
            'brand_type': 'fortimove_global',
            'product_name': '超强吸水速干毛巾',
            'generate_seo': True,
            'auto_replace_risks': True
        }

        print("   ⏳ API 호출 중...")
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()

        result = response.json()

        # 결과 출력
        print(f"\n   ✅ 처리 완료!")
        print(f"   작업 ID: {result['job_id']}")
        print(f"   상태: {result['status']}")
        print(f"   처리 시간: {result.get('processing_time_seconds', 0):.2f}초")

        # OCR 결과
        if 'analysis_report' in result:
            report = result['analysis_report']

            print(f"\n   📝 OCR 추출: {len(report['ocr_results'])}개")
            for ocr in report['ocr_results'][:3]:  # 첫 3개만
                print(f"      - {ocr['text']} (신뢰도: {ocr['confidence']:.2%})")

            # 번역 결과
            print(f"\n   🌐 번역: {len(report['translations'])}개")
            for trans in report['translations'][:3]:
                print(f"      - {trans['original']} → {trans['translated']}")

            # 리스크 탐지
            print(f"\n   ⚠️  리스크 탐지: {len(report['risks_detected'])}개")
            for risk in report['risks_detected']:
                print(f"      - {risk['risk_type']}: {risk['description']}")

            # 리스크 처리
            print(f"\n   🛡️  리스크 처리: {len(report['risks_processed'])}개")
            for proc in report['risks_processed']:
                print(f"      - {proc['risk_type']}: {proc['action']} ({proc['details']})")

        # SEO 메타데이터
        if 'seo_metadata' in result and result['seo_metadata']:
            seo = result['seo_metadata']

            print(f"\n   🎯 SEO 메타데이터:")
            print(f"   상품명 (3안):")
            for i, name in enumerate(seo['product_names'], 1):
                print(f"      {i}. {name}")

            print(f"\n   검색 태그: {', '.join(seo['search_tags'][:5])}...")
            print(f"   핵심 키워드: {', '.join(seo['keywords'])}")

        # 처리된 이미지
        if 'processed_images' in result:
            print(f"\n   🖼️  처리된 이미지: {len(result['processed_images'])}개")
            for img in result['processed_images']:
                print(f"      - {img['processed_filename']} ({img['width']}x{img['height']})")

        return True

    except Exception as e:
        print(f"   ❌ 처리 실패: {str(e)}")
        return False


def main():
    """메인 함수"""
    print("=" * 60)
    print("Fortimove 이미지 현지화 API 테스트 클라이언트")
    print("=" * 60)

    # 1. 헬스체크
    if not test_health():
        print("\n❌ API 서버가 실행 중이 아닙니다.")
        print("   docker-compose up -d 명령으로 서버를 시작하세요.")
        sys.exit(1)

    # 2. 이미지 처리
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test_image.jpg"

    if process_image(image_path):
        print("\n✅ 모든 테스트 통과!")
    else:
        print("\n❌ 테스트 실패")
        sys.exit(1)


if __name__ == "__main__":
    main()
