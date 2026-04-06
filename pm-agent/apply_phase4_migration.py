#!/usr/bin/env python3
"""
Phase 4 DB Migration Script
Applies 004_phase4_schema.sql to SQLite approval_queue.db
"""
import sqlite3
from pathlib import Path

def apply_migration():
    db_path = Path(__file__).parent / "data" / "approval_queue.db"
    migration_path = Path(__file__).parent / "migrations" / "004_phase4_schema.sql"

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return False

    if not migration_path.exists():
        print(f"❌ Migration file not found: {migration_path}")
        return False

    # Read migration SQL
    with open(migration_path, 'r', encoding='utf-8') as f:
        migration_sql = f.read()

    # Apply migration
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Execute migration SQL
        statements = []
        in_comment_block = False

        for line in migration_sql.split('\n'):
            stripped = line.strip()

            # Skip comment blocks
            if '/*' in stripped:
                in_comment_block = True
            if '*/' in stripped:
                in_comment_block = False
                continue

            if in_comment_block:
                continue

            # Skip single-line comments
            if stripped.startswith('--'):
                continue

            # Skip SELECT verification statements
            if stripped.upper().startswith('SELECT') and 'Migration' in stripped:
                continue

            # Add non-empty lines
            if stripped:
                statements.append(line)

        # Join and split by semicolon
        full_sql = '\n'.join(statements)
        statements = [s.strip() for s in full_sql.split(';') if s.strip()]

        executed_count = 0
        skipped_count = 0

        for i, statement in enumerate(statements, 1):
            if not statement:
                continue

            print(f"[{i}/{len(statements)}] Executing: {statement[:60]}...")
            try:
                cursor.execute(statement)
                executed_count += 1
            except Exception as e:
                # Ignore "column already exists" or "table already exists" errors
                error_str = str(e).lower()
                if "duplicate column" in error_str or "already exists" in error_str:
                    print(f"    ⚠️  Skipping (already exists)")
                    skipped_count += 1
                    continue
                else:
                    raise

        conn.commit()
        print(f"\n✅ Phase 4 migration applied successfully!")
        print(f"   Database: {db_path}")
        print(f"   Statements executed: {executed_count}")
        print(f"   Statements skipped: {skipped_count}")

        # Verify new columns in approval_queue
        cursor.execute("PRAGMA table_info(approval_queue)")
        columns = cursor.fetchall()

        new_columns = ['generated_naver_title', 'reviewed_naver_title', 'review_status']
        found_columns = [col[1] for col in columns if col[1] in new_columns]

        if found_columns:
            print(f"\n📊 approval_queue new columns: {', '.join(found_columns)}")

        # Check new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('image_review', 'review_history', 'export_log', 'review_status_config')")
        new_tables = [row[0] for row in cursor.fetchall()]

        if new_tables:
            print(f"📋 New tables created: {', '.join(new_tables)}")

        # Check review status configs
        cursor.execute("SELECT COUNT(*) FROM review_status_config")
        status_count = cursor.fetchone()[0]
        print(f"📝 Review status configs inserted: {status_count}")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    success = apply_migration()
    exit(0 if success else 1)
