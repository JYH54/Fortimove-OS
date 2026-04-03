"""
Phase 1 Content Generation API
상품 콘텐츠 생성 API 엔드포인트

아키텍처 재정렬 (2026-04-01):
- DetailPageStrategist: LLM 기반 상세페이지 콘텐츠 생성 (최우선)
- ProductContentGenerator: 룰 기반 보조 생성 (fallback)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sqlite3
import json
from pathlib import Path
from datetime import datetime
import logging

from product_content_generator import ProductContentGenerator, ComplianceFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/phase1", tags=["Phase1-Content-Generation"])

# Database path
DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"

def get_db():
    """Get database connection"""
    return sqlite3.connect(str(DB_PATH))


class ContentGenerationRequest(BaseModel):
    """콘텐츠 생성 요청"""
    regenerate: bool = False  # 기존 콘텐츠가 있어도 재생성할지


def get_review_data(review_id: str) -> Optional[Dict[str, Any]]:
    """리뷰 데이터 조회"""
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM approval_queue WHERE review_id = ?", (review_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    # Row를 dict로 변환
    review_data = dict(row)

    # JSON 필드 파싱
    json_fields = [
        'source_data_json', 'reviewed_images_json', 'raw_agent_output',
        'product_summary_json', 'detail_content_json', 'image_design_json',
        'sales_strategy_json', 'risk_assessment_json'
    ]

    for field in json_fields:
        if review_data.get(field):
            try:
                review_data[field] = json.loads(review_data[field])
            except:
                pass

    return review_data


def save_content_to_db(review_id: str, content_type: str, content: Dict[str, Any]):
    """생성된 콘텐츠를 DB에 저장"""
    conn = get_db()
    cursor = conn.cursor()

    field_map = {
        'summary': 'product_summary_json',
        'detail': 'detail_content_json',
        'image_design': 'image_design_json',
        'sales_strategy': 'sales_strategy_json',
        'risk_assessment': 'risk_assessment_json'
    }

    field_name = field_map.get(content_type)
    if not field_name:
        conn.close()
        raise ValueError(f"Unknown content type: {content_type}")

    content_json = json.dumps(content, ensure_ascii=False)
    now = datetime.now().isoformat()

    cursor.execute(f"""
        UPDATE approval_queue
        SET {field_name} = ?,
            content_generated_at = ?,
            updated_at = ?
        WHERE review_id = ?
    """, (content_json, now, now, review_id))

    conn.commit()
    conn.close()


@router.post("/review/{review_id}/generate-summary")
async def generate_product_summary(review_id: str, request: ContentGenerationRequest):
    """
    상품 핵심 요약 생성

    Returns:
        - positioning_summary: 포지셔닝 요약
        - usp_points: USP 포인트 (List)
        - target_customer: 타겟 고객
        - usage_scenarios: 사용 시나리오 (List)
        - differentiation_points: 차별화 포인트 (List)
        - search_intent_summary: 검색 의도 요약
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        # 이미 생성된 콘텐츠가 있고 재생성이 아니면 기존 반환
        if review_data.get('product_summary_json') and not request.regenerate:
            return {
                "status": "success",
                "message": "기존 생성된 요약 반환",
                "data": review_data['product_summary_json'],
                "regenerated": False
            }

        # 콘텐츠 생성
        generator = ProductContentGenerator()
        summary = generator.generate_product_summary(review_data)

        # DB 저장
        save_content_to_db(review_id, 'summary', summary)

        return {
            "status": "success",
            "message": "상품 요약 생성 완료",
            "data": summary,
            "regenerated": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상품 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/{review_id}/generate-detail-content")
async def generate_detail_content(review_id: str, request: ContentGenerationRequest):
    """
    상세페이지 콘텐츠 생성 (LLM 기반 - DetailPageStrategist)

    Returns:
        - main_title: 메인 타이틀
        - hook_copies: 훅 카피 (List)
        - key_benefits: 핵심 혜택 (List)
        - problem_scenarios: 문제 시나리오 (List)
        - solution_narrative: 솔루션 내러티브
        - target_users: 타겟 사용자
        - usage_guide: 사용 가이드
        - cautions: 주의사항
        - faq: FAQ (List of {q, a})
        - naver_body: 네이버 본문
        - coupang_body: 쿠팡 본문
        - short_ad_copies: 짧은 광고 문구 (List)
        - compliance_warnings: 컴플라이언스 경고 (List)
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        # 이미 생성된 콘텐츠가 있고 재생성이 아니면 기존 반환
        if review_data.get('detail_content_json') and not request.regenerate:
            return {
                "status": "success",
                "message": "기존 생성된 상세 콘텐츠 반환",
                "data": review_data['detail_content_json'],
                "regenerated": False,
                "generation_method": "cached"
            }

        # 상품 요약이 없으면 먼저 생성
        summary = review_data.get('product_summary_json')
        if not summary:
            generator = ProductContentGenerator()
            summary = generator.generate_product_summary(review_data)
            save_content_to_db(review_id, 'summary', summary)

        # LLM 기반 상세 콘텐츠 생성 (DetailPageStrategist 사용)
        try:
            from detail_page_strategist import DetailPageStrategist
            strategist = DetailPageStrategist()

            # source_data 준비
            source_data = review_data.get('source_data_json', {})
            if isinstance(source_data, str):
                source_data = json.loads(source_data)

            source_data['source_title'] = review_data.get('source_title', '')
            source_data['category'] = review_data.get('category', 'wellness')

            # DetailPageStrategist로 생성
            detail_content = strategist.generate_detail_page_content(
                product_summary=summary,
                source_data=source_data,
                category=review_data.get('category', 'wellness')
            )

            generation_method = "llm"
            logger.info(f"✅ LLM 기반 콘텐츠 생성 성공: {review_id}")

        except Exception as llm_error:
            # LLM 실패 시 룰 기반으로 fallback
            logger.warning(f"⚠️ LLM 생성 실패, 룰 기반 fallback: {llm_error}")
            generator = ProductContentGenerator()
            detail_content = generator.generate_detail_content(review_data, summary)
            generation_method = "rule-based (fallback)"

        # DB 저장
        save_content_to_db(review_id, 'detail', detail_content)

        return {
            "status": "success",
            "message": f"상세 콘텐츠 생성 완료 ({generation_method})",
            "data": detail_content,
            "regenerated": True,
            "generation_method": generation_method,
            "compliance_warnings": detail_content.get("compliance_warnings", [])
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"상세 콘텐츠 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/{review_id}/generate-image-design")
async def generate_image_design(review_id: str, request: ContentGenerationRequest):
    """
    이미지 디자인 가이드 생성

    Returns:
        - main_thumbnail_copy: 메인 썸네일 카피
        - sub_thumbnail_copies: 서브 썸네일 카피 (List)
        - banner_copy: 배너 카피
        - section_copies: 섹션별 카피 (List)
        - layout_guide: 레이아웃 가이드
        - tone_manner: 톤앤매너
        - forbidden_expressions: 금지 표현 (List)
        - generation_prompt: 이미지 생성 프롬프트
        - edit_prompt: 이미지 편집 프롬프트
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        # 이미 생성된 콘텐츠가 있고 재생성이 아니면 기존 반환
        if review_data.get('image_design_json') and not request.regenerate:
            return {
                "status": "success",
                "message": "기존 생성된 이미지 디자인 가이드 반환",
                "data": review_data['image_design_json'],
                "regenerated": False
            }

        # 상품 요약이 없으면 먼저 생성
        summary = review_data.get('product_summary_json')
        if not summary:
            generator = ProductContentGenerator()
            summary = generator.generate_product_summary(review_data)
            save_content_to_db(review_id, 'summary', summary)

        # 이미지 디자인 가이드 생성
        generator = ProductContentGenerator()
        image_design = generator.generate_image_design_guide(review_data, summary)

        # DB 저장
        save_content_to_db(review_id, 'image_design', image_design)

        return {
            "status": "success",
            "message": "이미지 디자인 가이드 생성 완료",
            "data": image_design,
            "regenerated": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 디자인 가이드 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/{review_id}/generate-sales-strategy")
async def generate_sales_strategy(review_id: str, request: ContentGenerationRequest):
    """
    판매 전략 생성

    Returns:
        - target_audience: 타겟 오디언스
        - ad_points: 광고 포인트 (List)
        - primary_keywords: 1차 키워드 (List)
        - secondary_keywords: 2차 키워드 (List)
        - hashtags: 해시태그 (List)
        - review_points: 리뷰 포인트 (List)
        - price_positioning: 가격 포지셔닝
        - sales_channels: 판매 채널 (List)
        - competitive_angles: 경쟁 우위 각도 (List)
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        # 이미 생성된 콘텐츠가 있고 재생성이 아니면 기존 반환
        if review_data.get('sales_strategy_json') and not request.regenerate:
            return {
                "status": "success",
                "message": "기존 생성된 판매 전략 반환",
                "data": review_data['sales_strategy_json'],
                "regenerated": False
            }

        # 상품 요약이 없으면 먼저 생성
        summary = review_data.get('product_summary_json')
        if not summary:
            generator = ProductContentGenerator()
            summary = generator.generate_product_summary(review_data)
            save_content_to_db(review_id, 'summary', summary)

        # 판매 전략 생성
        generator = ProductContentGenerator()
        sales_strategy = generator.generate_sales_strategy(review_data, summary)

        # DB 저장
        save_content_to_db(review_id, 'sales_strategy', sales_strategy)

        return {
            "status": "success",
            "message": "판매 전략 생성 완료",
            "data": sales_strategy,
            "regenerated": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"판매 전략 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/review/{review_id}/generate-all")
async def generate_all_content(review_id: str, request: ContentGenerationRequest):
    """
    전체 콘텐츠 한번에 생성

    - 상품 요약
    - 상세 콘텐츠
    - 이미지 디자인 가이드
    - 판매 전략
    - 리스크 평가
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        generator = ProductContentGenerator()

        # 1. 상품 요약 생성
        summary = generator.generate_product_summary(review_data)
        save_content_to_db(review_id, 'summary', summary)

        # 2. 상세 콘텐츠 생성
        detail_content = generator.generate_detail_content(review_data, summary)
        save_content_to_db(review_id, 'detail', detail_content)

        # 3. 이미지 디자인 가이드 생성
        image_design = generator.generate_image_design_guide(review_data, summary)
        save_content_to_db(review_id, 'image_design', image_design)

        # 4. 판매 전략 생성
        sales_strategy = generator.generate_sales_strategy(review_data, summary)
        save_content_to_db(review_id, 'sales_strategy', sales_strategy)

        # 5. 리스크 평가
        all_content = {
            'summary': summary,
            'detail': detail_content,
            'image_design': image_design,
            'sales_strategy': sales_strategy
        }
        risk_assessment = generator.assess_compliance_risks(review_data, all_content)
        save_content_to_db(review_id, 'risk_assessment', risk_assessment)

        return {
            "status": "success",
            "message": "전체 콘텐츠 생성 완료",
            "data": {
                "summary": summary,
                "detail_content": detail_content,
                "image_design": image_design,
                "sales_strategy": sales_strategy,
                "risk_assessment": risk_assessment
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"전체 콘텐츠 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review/{review_id}/content")
async def get_all_content(review_id: str):
    """
    생성된 콘텐츠 전체 조회
    """
    try:
        review_data = get_review_data(review_id)
        if not review_data:
            raise HTTPException(status_code=404, detail="Review not found")

        return {
            "status": "success",
            "review_id": review_id,
            "data": {
                "summary": review_data.get('product_summary_json'),
                "detail_content": review_data.get('detail_content_json'),
                "image_design": review_data.get('image_design_json'),
                "sales_strategy": review_data.get('sales_strategy_json'),
                "risk_assessment": review_data.get('risk_assessment_json'),
                "generated_at": review_data.get('content_generated_at'),
                "reviewed_at": review_data.get('content_reviewed_at'),
                "reviewer": review_data.get('content_reviewer')
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"콘텐츠 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
