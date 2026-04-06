#!/usr/bin/env python3
"""
Phase 2 DB Migration Script
Applies 002_phase2_schema.sql to SQLite approval_queue.db
"""
import sqlite3
from pathlib import Path

def apply_migration():
    db_path = Path(__file__).parent / "data" / "approval_queue.db"
    migration_path = Path(__file__).parent / "migrations" / "002_phase2_schema.sql"

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
        # Execute migration SQL (split by semicolon for multiple statements)
        # Skip comments and test queries inside /* */
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

            # Skip SELECT statements (they're just for verification)
            if stripped.upper().startswith('SELECT'):
                continue

            # Add non-empty lines
            if stripped:
                statements.append(line)

        # Join and split by semicolon
        full_sql = '\n'.join(statements)
        statements = [s.strip() for s in full_sql.split(';') if s.strip()]

        for i, statement in enumerate(statements, 1):
            if not statement:
                continue

            print(f"[{i}/{len(statements)}] Executing: {statement[:60]}...")
            try:
                cursor.execute(statement)
            except Exception as e:
                # Ignore "column already exists" errors
                if "duplicate column" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"    ⚠️  Skipping (already exists): {str(e)[:50]}")
                    continue
                else:
                    raise

        conn.commit()
        print(f"\n✅ Phase 2 migration applied successfully!")
        print(f"   Database: {db_path}")
        print(f"   Statements executed: {len(statements)}")

        # Verify new columns
        cursor.execute("PRAGMA table_info(approval_queue)")
        columns = cursor.fetchall()

        new_columns = ['score', 'decision', 'priority', 'reasons_json', 'content_status', 'scoring_updated_at']
        found_columns = [col[1] for col in columns if col[1] in new_columns]

        print(f"\n📊 New columns added: {', '.join(found_columns)}")

        # Check if channel_upload_queue table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_upload_queue'")
        if cursor.fetchone():
            print("📋 New table created: channel_upload_queue")

        return True

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    success = apply_migration()
    exit(0 if success else 1)
