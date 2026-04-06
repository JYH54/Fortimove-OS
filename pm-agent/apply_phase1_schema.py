#!/usr/bin/env python3
"""
Phase 1 Schema Migration - Add content generation JSON fields
"""
import sqlite3
from pathlib import Path
from datetime import datetime

def apply_phase1_schema():
    """Add JSON fields for product content generation"""
    db_path = Path(__file__).parent / "data" / "approval_queue.db"

    print(f"📊 Phase 1 Schema Migration 시작...")
    print(f"데이터베이스: {db_path}\n")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 새로운 JSON 필드 추가
    new_columns = [
        ("product_summary_json", "TEXT"),
        ("detail_content_json", "TEXT"),
        ("image_design_json", "TEXT"),
        ("sales_strategy_json", "TEXT"),
        ("risk_assessment_json", "TEXT"),
        ("content_generated_at", "TIMESTAMP"),
        ("content_reviewed_at", "TIMESTAMP"),
        ("content_reviewer", "TEXT")
    ]

    for col_name, col_type in new_columns:
        try:
            cursor.execute(f"ALTER TABLE approval_queue ADD COLUMN {col_name} {col_type}")
            print(f"✅ 컬럼 추가: {col_name} ({col_type})")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"⏭️  이미 존재: {col_name}")
            else:
                print(f"❌ 오류: {col_name} - {e}")

    conn.commit()

    # 검증
    cursor.execute("PRAGMA table_info(approval_queue)")
    columns = cursor.fetchall()

    print(f"\n📋 approval_queue 테이블 검증:")
    print(f"   총 컬럼 수: {len(columns)}개\n")

    # 새로 추가된 컬럼 확인
    added_cols = [col[1] for col in columns if col[1] in [name for name, _ in new_columns]]
    print(f"✅ Phase 1 컬럼 추가 완료:")
    for col in added_cols:
        print(f"   - {col}")

    conn.close()
    print(f"\n✅ Phase 1 Schema Migration 완료!\n")

if __name__ == "__main__":
    apply_phase1_schema()
