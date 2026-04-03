"""
Fortimove MD Dashboard - Premium Wellness Sourcing Intelligence
PostgreSQL + FastAPI + Jinja2 + TailwindCSS
"""
import asyncpg
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(title="Fortimove MD Dashboard")

# Jinja2 템플릿 설정
templates = Jinja2Templates(directory="templates")

# PostgreSQL 연결 정보
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "fortimove_images")
DB_USER = os.getenv("DB_USER", "fortimove")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")

# 커넥션 풀
db_pool = None


@app.on_event("startup")
async def startup():
    """앱 시작 시 DB 커넥션 풀 생성"""
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            min_size=2,
            max_size=10
        )
        logger.info(f"✅ PostgreSQL 커넥션 풀 생성: {DB_HOST}:{DB_PORT}/{DB_NAME}")
    except Exception as e:
        logger.error(f"❌ PostgreSQL 연결 실패: {e}")
        raise


@app.on_event("shutdown")
async def shutdown():
    """앱 종료 시 DB 커넥션 풀 닫기"""
    global db_pool
    if db_pool:
        await db_pool.close()
        logger.info("🔒 PostgreSQL 커넥션 풀 종료")


# === Helper Functions ===

async def fetch_products(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    workflow_status: str = 'pending',
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """상품 조회 (필터링 + 페이지네이션)"""
    query = "SELECT * FROM wellness_products WHERE 1=1"
    params = []
    param_count = 1

    # Workflow 상태 필터 (pending만 기본 조회)
    if workflow_status:
        query += f" AND workflow_status = ${param_count}"
        params.append(workflow_status)
        param_count += 1

    if region:
        query += f" AND region = ${param_count}"
        params.append(region)
        param_count += 1

    if category:
        query += f" AND category = ${param_count}"
        params.append(category)
        param_count += 1

    if risk_status:
        query += f" AND risk_status = ${param_count}"
        params.append(risk_status)
        param_count += 1

    query += f" ORDER BY created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_total_count(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    workflow_status: str = 'pending'
) -> int:
    """전체 상품 개수 조회"""
    query = "SELECT COUNT(*) FROM wellness_products WHERE 1=1"
    params = []
    param_count = 1

    if workflow_status:
        query += f" AND workflow_status = ${param_count}"
        params.append(workflow_status)
        param_count += 1

    if region:
        query += f" AND region = ${param_count}"
        params.append(region)
        param_count += 1

    if category:
        query += f" AND category = ${param_count}"
        params.append(category)
        param_count += 1

    if risk_status:
        query += f" AND risk_status = ${param_count}"
        params.append(risk_status)
        param_count += 1

    async with db_pool.acquire() as conn:
        result = await conn.fetchval(query, *params)
        return result or 0


async def get_summary_stats() -> Dict:
    """요약 통계 조회 (pending 상품만)"""
    async with db_pool.acquire() as conn:
        # 총 상품 수
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM wellness_products WHERE workflow_status = 'pending'"
        ) or 0

        # 통과 상품 수
        passed = await conn.fetchval(
            "SELECT COUNT(*) FROM wellness_products WHERE workflow_status = 'pending' AND risk_status = '통과'"
        ) or 0

        # 보류 상품 수
        pending = await conn.fetchval(
            "SELECT COUNT(*) FROM wellness_products WHERE workflow_status = 'pending' AND risk_status = '보류'"
        ) or 0

        # 최고 트렌드 점수
        max_score = await conn.fetchval(
            "SELECT MAX(trend_score) FROM wellness_products WHERE workflow_status = 'pending'"
        ) or 0

        # 지역별 분포
        region_rows = await conn.fetch(
            "SELECT region, COUNT(*) as count FROM wellness_products WHERE workflow_status = 'pending' GROUP BY region"
        )
        region_stats = {row['region']: row['count'] for row in region_rows}

        return {
            "total": total,
            "passed": passed,
            "pending": pending,
            "rejected": 0,
            "max_score": max_score,
            "region_stats": region_stats,
            "date": datetime.now().strftime('%Y-%m-%d')
        }


async def get_filter_options() -> Dict:
    """필터 옵션 조회"""
    async with db_pool.acquire() as conn:
        # 지역 목록
        regions = await conn.fetch(
            "SELECT DISTINCT region FROM wellness_products WHERE workflow_status = 'pending' ORDER BY region"
        )

        # 카테고리 목록
        categories = await conn.fetch(
            "SELECT DISTINCT category FROM wellness_products WHERE workflow_status = 'pending' AND category IS NOT NULL ORDER BY category"
        )

        return {
            "regions": [r['region'] for r in regions],
            "categories": [c['category'] for c in categories],
            "risk_statuses": ['통과', '보류']
        }


# === API 엔드포인트 ===

@app.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    region: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    risk_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1)
):
    """메인 대시보드 페이지"""
    try:
        # 요약 통계
        summary = await get_summary_stats()

        # 필터 옵션
        filter_options = await get_filter_options()

        # 페이지네이션 설정
        limit = 50
        offset = (page - 1) * limit

        # 상품 조회
        products = await fetch_products_advanced(
            region=region,
            category=category,
            risk_status=risk_status,
            workflow_status='pending',
            limit=limit,
            offset=offset
        )

        # 전체 개수 조회
        total_count = await get_total_count_advanced(
            region=region,
            category=category,
            risk_status=risk_status,
            workflow_status='pending'
        )

        # 총 페이지 수 계산
        total_pages = (total_count + limit - 1) // limit

        return templates.TemplateResponse("index.html", {
            "request": request,
            "summary": summary,
            "filter_options": filter_options,
            "products": products,
            "current_page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "region": region,
            "category": category,
            "risk_status": risk_status
        })
    except Exception as e:
        logger.error(f"대시보드 렌더링 실패: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/products", response_class=JSONResponse)
async def get_products_api(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100)
):
    """상품 API (JSON)"""
    try:
        offset = (page - 1) * limit

        products = await fetch_products_advanced(
            region=region,
            category=category,
            risk_status=risk_status,
            workflow_status='pending',
            limit=limit,
            offset=offset
        )

        total_count = await get_total_count_advanced(
            region=region,
            category=category,
            risk_status=risk_status,
            workflow_status='pending'
        )

        return {
            "success": True,
            "count": len(products),
            "total_count": total_count,
            "page": page,
            "total_pages": (total_count + limit - 1) // limit,
            "data": products
        }
    except Exception as e:
        logger.error(f"상품 API 실패: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/stats", response_class=JSONResponse)
async def get_stats_api():
    """통계 API (JSON)"""
    try:
        stats = await get_summary_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"통계 API 실패: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/products/{product_id}/status", response_class=JSONResponse)
async def update_product_status(product_id: int, status: str = Query(...)):
    """상품 워크플로우 상태 업데이트 API (Slack 알림 포함)"""
    try:
        # 상태 검증
        if status not in ['pending', 'sourced', 'discarded']:
            return {"success": False, "error": f"Invalid status: {status}"}

        # 1. 상품 정보 조회
        async with db_pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT * FROM wellness_products WHERE id = $1",
                product_id
            )

            if not product:
                return {"success": False, "error": "Product not found"}

            # 2. 히스토리 기록
            old_status = product['workflow_status']
            await conn.execute('''
                INSERT INTO product_history (product_id, action, old_status, new_status, changed_by, notes)
                VALUES ($1, $2, $3, $4, $5, $6)
            ''',
                product_id,
                f"status_change_{status}",
                old_status,
                status,
                'dashboard_user',
                f"상태 변경: {old_status} → {status}"
            )

            # 3. 상태 업데이트
            await conn.execute('''
                UPDATE wellness_products
                SET workflow_status = $1, updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
            ''', status, product_id)

        # 4. Slack 알림 (비동기)
        await send_slack_notification(product_id, dict(product), status)

        logger.info(f"✅ 상품 ID {product_id} 상태 변경: {status}")
        return {"success": True, "product_id": product_id, "new_status": status}

    except Exception as e:
        logger.error(f"상태 업데이트 실패 (ID: {product_id}): {e}")
        return {"success": False, "error": str(e)}


# === 중기 개선: Slack 워크플로우 자동화 ===

async def send_slack_notification(product_id: int, product: Dict, status: str):
    """Slack 알림 전송"""
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("⚠️ SLACK_WEBHOOK_URL 미설정: 알림을 건너뜁니다.")
        return

    try:
        # 상태에 따른 메시지 구성
        if status == 'sourced':
            color = "#36a64f"  # 녹색
            emoji = "✅"
            title = "상품 채택됨"
        elif status == 'discarded':
            color = "#d32f2f"  # 빨강
            emoji = "❌"
            title = "상품 거부됨"
        else:
            color = "#ffc107"  # 노랑
            emoji = "⏳"
            title = "상품 보류됨"

        message = {
            "username": "Fortimove MD Dashboard",
            "icon_emoji": ":robot_face:",
            "attachments": [
                {
                    "color": color,
                    "title": f"{emoji} {title}",
                    "fields": [
                        {"title": "상품 ID", "value": str(product_id), "short": True},
                        {"title": "상품명", "value": product.get('product_name', 'N/A')[:100], "short": True},
                        {"title": "브랜드", "value": product.get('brand', 'N/A'), "short": True},
                        {"title": "지역", "value": product.get('region', 'N/A'), "short": True},
                        {"title": "가격", "value": product.get('price', 'N/A'), "short": True},
                        {"title": "카테고리", "value": product.get('category', 'N/A'), "short": True},
                        {"title": "트렌드 점수", "value": f"{product.get('trend_score', 0)}/100", "short": True},
                        {"title": "리스크 상태", "value": product.get('risk_status', 'N/A'), "short": True},
                    ],
                    "footer": "Fortimove Wellness Scout",
                    "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

        # 비동기 HTTP 요청
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message) as response:
                if response.status == 200:
                    logger.info(f"✅ Slack 알림 전송 성공: 상품 ID {product_id}")
                else:
                    logger.error(f"❌ Slack 알림 전송 실패: {response.status}")

    except Exception as e:
        logger.error(f"❌ Slack 알림 오류: {e}")


@app.get("/health", response_class=JSONResponse)
async def health_check():
    """헬스 체크"""
    try:
        # DB 연결 확인
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        return {"status": "healthy", "service": "Fortimove MD Dashboard (PostgreSQL)"}
    except Exception as e:
        logger.error(f"헬스 체크 실패: {e}")
        return {"status": "unhealthy", "error": str(e)}

# === 추가 기능: 날짜 필터, 검색, Excel 내보내기 ===

from datetime import datetime, timedelta
from fastapi.responses import StreamingResponse
import io
import csv

async def fetch_products_advanced(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    workflow_status: str = 'pending',
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict]:
    """상품 조회 (고급 필터링: 날짜, 검색)"""
    query = "SELECT * FROM wellness_products WHERE 1=1"
    params = []
    param_count = 1

    # Workflow 상태 필터
    if workflow_status:
        query += f" AND workflow_status = ${param_count}"
        params.append(workflow_status)
        param_count += 1

    # 날짜 범위 필터
    if date_from:
        query += f" AND date >= ${param_count}"
        params.append(date_from)
        param_count += 1

    if date_to:
        query += f" AND date <= ${param_count}"
        params.append(date_to)
        param_count += 1

    # 검색 (상품명, 브랜드, 설명)
    if search:
        query += f" AND (product_name ILIKE ${param_count} OR brand ILIKE ${param_count} OR description ILIKE ${param_count})"
        params.append(f"%{search}%")
        param_count += 1

    # 기존 필터
    if region:
        query += f" AND region = ${param_count}"
        params.append(region)
        param_count += 1

    if category:
        query += f" AND category = ${param_count}"
        params.append(category)
        param_count += 1

    if risk_status:
        query += f" AND risk_status = ${param_count}"
        params.append(risk_status)
        param_count += 1

    query += f" ORDER BY created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        return [dict(row) for row in rows]


async def get_total_count_advanced(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    workflow_status: str = 'pending',
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None
) -> int:
    """전체 상품 개수 조회 (고급 필터 포함)"""
    query = "SELECT COUNT(*) FROM wellness_products WHERE 1=1"
    params = []
    param_count = 1

    if workflow_status:
        query += f" AND workflow_status = ${param_count}"
        params.append(workflow_status)
        param_count += 1

    if date_from:
        query += f" AND date >= ${param_count}"
        params.append(date_from)
        param_count += 1

    if date_to:
        query += f" AND date <= ${param_count}"
        params.append(date_to)
        param_count += 1

    if search:
        query += f" AND (product_name ILIKE ${param_count} OR brand ILIKE ${param_count} OR description ILIKE ${param_count})"
        params.append(f"%{search}%")
        param_count += 1

    if region:
        query += f" AND region = ${param_count}"
        params.append(region)
        param_count += 1

    if category:
        query += f" AND category = ${param_count}"
        params.append(category)
        param_count += 1

    if risk_status:
        query += f" AND risk_status = ${param_count}"
        params.append(risk_status)
        param_count += 1

    async with db_pool.acquire() as conn:
        result = await conn.fetchval(query, *params)
        return result or 0


@app.get("/api/product/{product_id}", response_class=JSONResponse)
async def get_product_detail(product_id: int):
    """상품 상세 정보 조회 (모달용)"""
    try:
        async with db_pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT * FROM wellness_products WHERE id = $1",
                product_id
            )

            if not product:
                return {"success": False, "error": "Product not found"}

            return {"success": True, "data": dict(product)}

    except Exception as e:
        logger.error(f"상품 상세 조회 실패 (ID: {product_id}): {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/export/csv", response_class=StreamingResponse)
async def export_csv(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None
):
    """CSV 내보내기"""
    try:
        # 모든 데이터 조회 (limit 없음)
        products = await fetch_products_advanced(
            region=region,
            category=category,
            risk_status=risk_status,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=10000,  # 최대 10,000개
            offset=0
        )

        # CSV 생성
        output = io.StringIO()
        writer = csv.writer(output)

        # 헤더
        writer.writerow([
            'ID', '날짜', '지역', '출처', '상품명', '브랜드', '가격',
            '카테고리', '트렌드점수', '한국수요', '리스크상태', '설명', 'URL'
        ])

        # 데이터
        for p in products:
            writer.writerow([
                p.get('id', ''),
                p.get('date', ''),
                p.get('region', ''),
                p.get('source', ''),
                p.get('product_name', ''),
                p.get('brand', ''),
                p.get('price', ''),
                p.get('category', ''),
                p.get('trend_score', ''),
                p.get('korea_demand', ''),
                p.get('risk_status', ''),
                p.get('description', ''),
                p.get('url', '')
            ])

        # 파일명 생성
        filename = f"wellness_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # 스트림 반환
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"CSV 내보내기 실패: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/export/excel", response_class=StreamingResponse)
async def export_excel(
    region: Optional[str] = None,
    category: Optional[str] = None,
    risk_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None
):
    """Excel 내보내기 (CSV 포맷, Excel 호환)"""
    # Excel은 CSV와 동일하게 처리 (간단한 구현)
    return await export_csv(region, category, risk_status, date_from, date_to, search)


# === 중기 개선: AI 리스크 재평가 ===

from anthropic import Anthropic
import pandas as pd
from fastapi import UploadFile, File

@app.post("/api/product/{product_id}/reassess", response_class=JSONResponse)
async def reassess_risk(product_id: int):
    """AI로 상품 리스크 재평가"""
    try:
        # 1. 상품 정보 조회
        async with db_pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT * FROM wellness_products WHERE id = $1",
                product_id
            )

            if not product:
                return {"success": False, "error": "Product not found"}

        # 2. Claude API 호출
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            return {"success": False, "error": "ANTHROPIC_API_KEY not configured"}

        client = Anthropic(api_key=anthropic_key)

        prompt = f"""당신은 글로벌 웰니스 상품 소싱 전문가입니다. 아래 상품의 한국 시장 진입 리스크를 재평가해주세요.

상품 정보:
- 상품명: {product['product_name']}
- 브랜드: {product.get('brand', 'N/A')}
- 카테고리: {product.get('category', 'N/A')}
- 설명: {product.get('description', 'N/A')}
- 지역: {product['region']}
- 가격: {product.get('price', 'N/A')}
- 출처: {product['source']}

평가 기준:
1. 한국 식약처 규제 (건강기능식품, 의료기기 등)
2. 통관 가능성 (개인통관, 병행수입 등)
3. 지식재산권 리스크 (디자인, 상표권)
4. 플랫폼 제재 가능성 (네이버, 쿠팡)
5. 시장 경쟁도 및 수요

아래 JSON 형식으로 답변해주세요:
{{
  "risk_status": "통과" 또는 "보류",
  "risk_score": 0-100 (낮을수록 안전),
  "risk_factors": ["위험 요소1", "위험 요소2"],
  "recommendations": ["개선안1", "개선안2"],
  "market_analysis": "시장 분석 요약 (2-3문장)"
}}"""

        message = client.messages.create(
            model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        # 3. 응답 파싱
        response_text = message.content[0].text

        # JSON 추출 (```json 마크다운 제거)
        import json
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            analysis = json.loads(json_match.group())
        else:
            return {"success": False, "error": "Failed to parse AI response"}

        # 4. DB 업데이트
        async with db_pool.acquire() as conn:
            await conn.execute('''
                UPDATE wellness_products
                SET
                    risk_status = $1,
                    risk_score = $2,
                    risk_factors = $3,
                    recommendations = $4,
                    market_analysis = $5,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $6
            ''',
                analysis['risk_status'],
                float(analysis.get('risk_score', 0)),
                json.dumps(analysis.get('risk_factors', []), ensure_ascii=False),
                json.dumps(analysis.get('recommendations', []), ensure_ascii=False),
                analysis.get('market_analysis', ''),
                product_id
            )

        logger.info(f"✅ AI 재평가 완료: 상품 ID {product_id} - {analysis['risk_status']}")

        return {
            "success": True,
            "product_id": product_id,
            "analysis": analysis
        }

    except Exception as e:
        logger.error(f"AI 재평가 실패 (ID: {product_id}): {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# === 중기 개선: 엑셀 일괄 상품 등록 ===

@app.post("/api/products/bulk-upload", response_class=JSONResponse)
async def bulk_upload_products(file: UploadFile = File(...)):
    """엑셀 파일로 상품 일괄 등록"""
    try:
        # 1. 파일 확장자 검증
        if not file.filename.endswith(('.xlsx', '.xls', '.csv')):
            return {"success": False, "error": "Excel 또는 CSV 파일만 업로드 가능합니다."}

        # 2. 파일 읽기
        contents = await file.read()

        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

        # 3. 필수 컬럼 검증
        required_cols = ['product_name', 'region', 'date']
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            return {
                "success": False,
                "error": f"필수 컬럼 누락: {', '.join(missing_cols)}",
                "required_columns": required_cols,
                "provided_columns": list(df.columns)
            }

        # 4. 데이터 정제
        df = df.fillna('')

        # 5. DB에 삽입
        inserted_count = 0
        errors = []

        async with db_pool.acquire() as conn:
            for idx, row in df.iterrows():
                try:
                    await conn.execute('''
                        INSERT INTO wellness_products (
                            date, region, source, product_name, brand, price,
                            category, trend_score, korea_demand, risk_status,
                            description, url, workflow_status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ''',
                        str(row.get('date', datetime.now().strftime('%Y-%m-%d'))),
                        str(row['region']),
                        str(row.get('source', 'Bulk Upload')),
                        str(row['product_name']),
                        str(row.get('brand', '')),
                        str(row.get('price', '')),
                        str(row.get('category', '')),
                        int(row.get('trend_score', 0)) if row.get('trend_score') else 0,
                        str(row.get('korea_demand', '')),
                        str(row.get('risk_status', '보류')),
                        str(row.get('description', '')),
                        str(row.get('url', '')),
                        'pending'
                    )
                    inserted_count += 1

                except Exception as e:
                    errors.append(f"행 {idx + 2}: {str(e)}")
                    logger.error(f"행 {idx + 2} 삽입 실패: {e}")

        logger.info(f"✅ 일괄 등록 완료: {inserted_count}개 성공, {len(errors)}개 실패")

        return {
            "success": True,
            "inserted_count": inserted_count,
            "total_rows": len(df),
            "errors": errors[:10]  # 최대 10개 오류만 반환
        }

    except Exception as e:
        logger.error(f"일괄 업로드 실패: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/api/products/template", response_class=StreamingResponse)
async def download_template():
    """엑셀 업로드 템플릿 다운로드"""
    try:
        # 템플릿 CSV 생성
        output = io.StringIO()
        writer = csv.writer(output)

        # 헤더 (필수 컬럼 + 선택 컬럼)
        writer.writerow([
            'date', 'region', 'source', 'product_name', 'brand', 'price',
            'category', 'trend_score', 'korea_demand', 'risk_status',
            'description', 'url'
        ])

        # 샘플 데이터 1개
        writer.writerow([
            '2026-03-29',
            'japan',
            'iHerb JP',
            '샘플 상품명',
            '샘플 브랜드',
            '$29.99',
            '영양제/보충제',
            '75',
            '높음',
            '보류',
            '샘플 상품 설명',
            'https://example.com/product'
        ])

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=wellness_products_template.csv"}
        )

    except Exception as e:
        logger.error(f"템플릿 다운로드 실패: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# === 중기 개선: 히스토리 추적 ===

@app.get("/api/product/{product_id}/history", response_class=JSONResponse)
async def get_product_history(product_id: int):
    """상품 히스토리 조회"""
    try:
        async with db_pool.acquire() as conn:
            history = await conn.fetch('''
                SELECT * FROM product_history
                WHERE product_id = $1
                ORDER BY created_at DESC
                LIMIT 100
            ''', product_id)

            return {
                "success": True,
                "product_id": product_id,
                "count": len(history),
                "history": [dict(h) for h in history]
            }

    except Exception as e:
        logger.error(f"히스토리 조회 실패 (ID: {product_id}): {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/history/recent", response_class=JSONResponse)
async def get_recent_history(limit: int = Query(50, ge=1, le=500)):
    """최근 히스토리 조회 (전체 상품)"""
    try:
        async with db_pool.acquire() as conn:
            history = await conn.fetch('''
                SELECT
                    h.*,
                    p.product_name,
                    p.brand,
                    p.region
                FROM product_history h
                LEFT JOIN wellness_products p ON h.product_id = p.id
                ORDER BY h.created_at DESC
                LIMIT $1
            ''', limit)

            return {
                "success": True,
                "count": len(history),
                "history": [dict(h) for h in history]
            }

    except Exception as e:
        logger.error(f"최근 히스토리 조회 실패: {e}")
        return {"success": False, "error": str(e)}
