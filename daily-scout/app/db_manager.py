"""
PostgreSQL Database Manager for Daily Wellness Scout
SQLite에서 PostgreSQL로 마이그레이션
"""
import asyncpg
import os
import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL 데이터베이스 관리자"""

    def __init__(self):
        # PostgreSQL 연결 정보 (기존 db 컨테이너 사용)
        self.db_host = os.getenv("DB_HOST", "db")
        self.db_port = int(os.getenv("DB_PORT", "5432"))
        self.db_name = os.getenv("DB_NAME", "fortimove_images")
        self.db_user = os.getenv("DB_USER", "fortimove")
        self.db_password = os.getenv("DB_PASSWORD", "changeme")

        self.pool = None

    async def init_pool(self):
        """커넥션 풀 초기화"""
        try:
            self.pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info(f"✅ PostgreSQL 커넥션 풀 생성 완료: {self.db_host}:{self.db_port}/{self.db_name}")

            # 스키마 초기화
            await self.init_schema()

        except Exception as e:
            logger.error(f"❌ PostgreSQL 연결 실패: {e}")
            raise

    async def close_pool(self):
        """커넥션 풀 종료"""
        if self.pool:
            await self.pool.close()
            logger.info("🔒 PostgreSQL 커넥션 풀 종료")

    async def init_schema(self):
        """테이블 스키마 생성"""
        async with self.pool.acquire() as conn:
            # products 테이블
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS wellness_products (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    region VARCHAR(50) NOT NULL,
                    source VARCHAR(255),
                    product_name TEXT NOT NULL,
                    brand VARCHAR(255),
                    price VARCHAR(100),
                    category VARCHAR(100),
                    trend_score INTEGER,
                    korea_demand VARCHAR(50),
                    risk_status VARCHAR(50),
                    description TEXT,
                    url TEXT,
                    workflow_status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 인덱스 생성
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_wellness_date ON wellness_products(date DESC);
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_wellness_region ON wellness_products(region);
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_wellness_workflow ON wellness_products(workflow_status);
            ''')
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_wellness_created ON wellness_products(created_at DESC);
            ''')

            # daily_stats 테이블
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS wellness_daily_stats (
                    id SERIAL PRIMARY KEY,
                    date DATE UNIQUE NOT NULL,
                    total_analyzed INTEGER DEFAULT 0,
                    passed INTEGER DEFAULT 0,
                    pending INTEGER DEFAULT 0,
                    rejected INTEGER DEFAULT 0,
                    top_category VARCHAR(100),
                    insights TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            logger.info("✅ PostgreSQL 스키마 초기화 완료")

    async def save_products(self, products: List[Dict], date: str):
        """상품 데이터 저장"""
        if not products:
            logger.warning("저장할 상품이 없습니다")
            return 0

        # ✅ FIX: 문자열 날짜를 datetime.date 객체로 변환
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()

        async with self.pool.acquire() as conn:
            inserted = 0
            for product in products:
                try:
                    # workflow_status는 항상 'pending'으로 시작
                    await conn.execute('''
                        INSERT INTO wellness_products (
                            date, region, source, product_name, brand, price,
                            category, trend_score, korea_demand, risk_status,
                            description, url, workflow_status
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ''',
                        date_obj,  # ✅ 변경: date → date_obj
                        product.get('region', ''),
                        product.get('source', ''),
                        product.get('product_name', ''),
                        product.get('brand', ''),
                        product.get('price', ''),
                        product.get('category', ''),
                        product.get('trend_score', 0),
                        product.get('korea_demand', ''),
                        product.get('risk_status', '통과'),
                        product.get('description', ''),
                        product.get('url', ''),
                        'pending'  # 기본 상태: 대기 중
                    )
                    inserted += 1
                except Exception as e:
                    logger.error(f"상품 저장 실패: {product.get('product_name')}: {e}")

            logger.info(f"✅ {inserted}개 상품 저장 완료")
            return inserted

    async def save_daily_stats(self, stats: Dict):
        """일일 통계 저장"""
        async with self.pool.acquire() as conn:
            try:
                # ✅ FIX: stats['date']가 문자열이면 datetime.date 객체로 변환
                date_value = stats['date']
                if isinstance(date_value, str):
                    date_value = datetime.strptime(date_value, '%Y-%m-%d').date()

                await conn.execute('''
                    INSERT INTO wellness_daily_stats (
                        date, total_analyzed, passed, pending, rejected,
                        top_category, insights
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (date)
                    DO UPDATE SET
                        total_analyzed = EXCLUDED.total_analyzed,
                        passed = EXCLUDED.passed,
                        pending = EXCLUDED.pending,
                        rejected = EXCLUDED.rejected,
                        top_category = EXCLUDED.top_category,
                        insights = EXCLUDED.insights
                ''',
                    date_value,  # ✅ 변경: stats['date'] → date_value
                    stats.get('total_analyzed', 0),
                    stats.get('passed', 0),
                    stats.get('pending', 0),
                    stats.get('rejected', 0),
                    stats.get('top_category', ''),
                    stats.get('insights', '')
                )
                logger.info(f"✅ 일일 통계 저장 완료: {date_value}")
            except Exception as e:
                logger.error(f"통계 저장 실패: {e}")

    async def get_products(
        self,
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

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    async def get_total_count(
        self,
        region: Optional[str] = None,
        category: Optional[str] = None,
        risk_status: Optional[str] = None,
        workflow_status: str = 'pending'
    ) -> int:
        """전체 상품 개수 조회 (페이지네이션용)"""
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

        async with self.pool.acquire() as conn:
            result = await conn.fetchval(query, *params)
            return result or 0

    async def get_summary_stats(self, date: Optional[str] = None) -> Dict:
        """요약 통계 조회"""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        async with self.pool.acquire() as conn:
            # 총 상품 수 (pending만)
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
                "date": date
            }

    async def get_filter_options(self) -> Dict:
        """필터 옵션 조회"""
        async with self.pool.acquire() as conn:
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

    async def update_workflow_status(self, product_id: int, new_status: str) -> bool:
        """상품 워크플로우 상태 업데이트"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute('''
                    UPDATE wellness_products
                    SET workflow_status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                ''', new_status, product_id)
                logger.info(f"✅ 상품 ID {product_id} 상태 변경: {new_status}")
                return True
            except Exception as e:
                logger.error(f"상태 업데이트 실패 (ID: {product_id}): {e}")
                return False
