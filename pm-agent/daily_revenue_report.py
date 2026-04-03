#!/usr/bin/env python3
"""
일일 수익 리포트 생성기
- Approval Queue 데이터 기반
- Auto-Approval 통계
- 예상 수익 계산
"""
import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

class DailyRevenueReporter:
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "data", "approval_queue.db")

        self.db_path = db_path

    def get_db_connection(self):
        """SQLite DB 연결"""
        return sqlite3.connect(self.db_path)

    def get_daily_stats(self, date_str: str = None) -> Dict[str, Any]:
        """
        특정 날짜의 통계 (default: 오늘)

        Returns:
            {
                'total_processed': int,
                'auto_approved': int,
                'manual_review': int,
                'rejected': int,
                'estimated_revenue': float,
                'estimated_margin': float
            }
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            # 오늘 생성된 항목 조회
            query = """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN reviewer_status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN reviewer_status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN reviewer_status = 'needs_edit' THEN 1 ELSE 0 END) as needs_edit,
                    SUM(CASE WHEN reviewer_status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM approval_queue
                WHERE DATE(created_at) = ?
            """
            cursor.execute(query, (date_str,))
            row = cursor.fetchone()

            total, approved, pending, needs_edit, rejected = row

            # 승인된 상품의 예상 수익 계산
            revenue_query = """
                SELECT source_data_json
                FROM approval_queue
                WHERE DATE(created_at) = ? AND reviewer_status = 'approved'
            """
            cursor.execute(revenue_query, (date_str,))

            estimated_revenue = 0.0
            estimated_margin = 0.0

            for (source_data_str,) in cursor.fetchall():
                try:
                    source_data = json.loads(source_data_str)

                    # Pricing 결과에서 최종 가격과 마진 추출
                    pricing_result = source_data.get('all_results', {}).get('pricing', {}).get('output', {})

                    final_price = pricing_result.get('final_price', 0)
                    margin_amount = pricing_result.get('margin_amount', 0)

                    estimated_revenue += final_price
                    estimated_margin += margin_amount

                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            return {
                'date': date_str,
                'total_processed': total or 0,
                'auto_approved': approved or 0,
                'manual_review': (pending or 0) + (needs_edit or 0),
                'rejected': rejected or 0,
                'estimated_revenue': round(estimated_revenue, 0),
                'estimated_margin': round(estimated_margin, 0),
                'auto_approval_rate': (approved / total * 100) if total > 0 else 0
            }

        finally:
            cursor.close()
            conn.close()

    def get_top_products(self, date_str: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        오늘 승인된 상품 중 마진이 높은 상위 N개
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        conn = self.get_db_connection()
        cursor = conn.cursor()

        try:
            query = """
                SELECT review_id, source_title, source_data_json, created_at
                FROM approval_queue
                WHERE DATE(created_at) = ? AND reviewer_status = 'approved'
                ORDER BY created_at DESC
            """
            cursor.execute(query, (date_str,))

            products = []

            for row in cursor.fetchall():
                queue_id, title, source_data_str, created_at = row

                try:
                    source_data = json.loads(source_data_str)
                    pricing_result = source_data.get('all_results', {}).get('pricing', {}).get('output', {})

                    final_price = pricing_result.get('final_price', 0)
                    margin_amount = pricing_result.get('margin_amount', 0)
                    margin_rate = pricing_result.get('margin_rate', 0)

                    products.append({
                        'title': title,
                        'final_price': final_price,
                        'margin_amount': margin_amount,
                        'margin_rate': margin_rate
                    })

                except (json.JSONDecodeError, KeyError, TypeError):
                    continue

            # 마진 금액 기준 정렬
            products.sort(key=lambda x: x['margin_amount'], reverse=True)

            return products[:limit]

        finally:
            cursor.close()
            conn.close()

    def generate_report(self, date_str: str = None) -> str:
        """
        일일 수익 리포트 텍스트 생성
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        stats = self.get_daily_stats(date_str)
        top_products = self.get_top_products(date_str, limit=10)

        report = []
        report.append("=" * 80)
        report.append(f"📊 Fortimove 일일 수익 리포트 - {date_str}")
        report.append("=" * 80)
        report.append("")

        # 1. 전체 통계
        report.append("## 1. 처리 통계")
        report.append(f"  • 총 분석 상품: {stats['total_processed']}개")
        report.append(f"  • 자동 승인 (Golden Pass): {stats['auto_approved']}개 ({stats['auto_approval_rate']:.1f}%)")
        report.append(f"  • 수동 검토 필요: {stats['manual_review']}개")
        report.append(f"  • 거부: {stats['rejected']}개")
        report.append("")

        # 2. 수익 분석
        report.append("## 2. 예상 수익")
        report.append(f"  • 총 판매 예상액: ₩{stats['estimated_revenue']:,.0f}")
        report.append(f"  • 예상 순이익: ₩{stats['estimated_margin']:,.0f}")
        report.append("")

        # 평균 마진률 계산
        avg_margin_rate = 0
        if stats['auto_approved'] > 0 and stats['estimated_revenue'] > 0:
            avg_margin_rate = (stats['estimated_margin'] / stats['estimated_revenue']) * 100

        report.append(f"  • 평균 마진율: {avg_margin_rate:.1f}%")
        report.append(f"  • 상품당 평균 수익: ₩{stats['estimated_margin'] / stats['auto_approved'] if stats['auto_approved'] > 0 else 0:,.0f}")
        report.append("")

        # 3. 고마진 상품 Top 10
        if top_products:
            report.append("## 3. 고마진 승인 상품 (Top 10)")
            for idx, product in enumerate(top_products, 1):
                report.append(f"  {idx}. {product['title'][:50]}")
                report.append(f"     판매가: ₩{product['final_price']:,.0f} | 마진: ₩{product['margin_amount']:,.0f} ({product['margin_rate'] * 100:.1f}%)")
                report.append("")
        else:
            report.append("## 3. 고마진 승인 상품")
            report.append("  (오늘 승인된 상품이 없습니다)")
            report.append("")

        # 4. 다음 액션
        report.append("## 4. 다음 액션")
        if stats['manual_review'] > 0:
            report.append(f"  • {stats['manual_review']}개 상품 수동 검토 필요")
            report.append(f"  • 검토 페이지: http://localhost:8001/review/list")
        else:
            report.append("  • 모든 상품 처리 완료 ✅")

        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def generate_weekly_summary(self) -> str:
        """
        주간 요약 리포트 (최근 7일)
        """
        report = []
        report.append("=" * 80)
        report.append(f"📈 Fortimove 주간 수익 요약 (최근 7일)")
        report.append("=" * 80)
        report.append("")

        total_revenue = 0
        total_margin = 0
        total_products = 0

        for i in range(7):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')

            stats = self.get_daily_stats(date_str)

            total_revenue += stats['estimated_revenue']
            total_margin += stats['estimated_margin']
            total_products += stats['auto_approved']

            report.append(f"{date_str}: {stats['auto_approved']}개 승인 | 수익 ₩{stats['estimated_margin']:,.0f}")

        report.append("")
        report.append("## 주간 합계")
        report.append(f"  • 승인 상품: {total_products}개")
        report.append(f"  • 총 판매 예상액: ₩{total_revenue:,.0f}")
        report.append(f"  • 예상 순이익: ₩{total_margin:,.0f}")
        report.append(f"  • 일평균 수익: ₩{total_margin / 7:,.0f}")
        report.append("")
        report.append("=" * 80)

        return "\n".join(report)


def main():
    """메인 실행 함수"""
    reporter = DailyRevenueReporter()

    # 오늘 리포트
    today_report = reporter.generate_report()
    print(today_report)

    # 주간 요약
    print("\n\n")
    weekly_report = reporter.generate_weekly_summary()
    print(weekly_report)

    # 파일 저장 (옵션)
    output_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(output_dir, exist_ok=True)

    today_str = datetime.now().strftime('%Y-%m-%d')
    output_file = os.path.join(output_dir, f"daily_revenue_{today_str}.txt")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(today_report)
        f.write("\n\n")
        f.write(weekly_report)

    print(f"\n\n✅ 리포트 저장 완료: {output_file}")


if __name__ == "__main__":
    main()
