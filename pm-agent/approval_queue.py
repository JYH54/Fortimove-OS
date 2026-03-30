import sqlite3
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ApprovalQueueManager:
    VALID_STATUSES = {"pending", "approved", "needs_edit", "rejected"}
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Use provided env var, or fallback to relative data directory.
            db_path = os.getenv("APPROVAL_DB_PATH", "data/approval_queue.db")
            
        self.db_path = db_path
        
        # Ensure parent directory exists. memory DB strings don't have parents.
        if self.db_path != ":memory:":
            parent_dir = os.path.dirname(os.path.abspath(self.db_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
                
        self._init_db()

    def _init_db(self):
        """명시적으로 테이블을 고정하고 초기화 진행"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS approval_queue (
                    review_id TEXT PRIMARY KEY,
                    source_type TEXT NOT NULL,
                    source_title TEXT NOT NULL,
                    registration_title_ko TEXT,
                    registration_status TEXT NOT NULL,
                    needs_human_review BOOLEAN NOT NULL,
                    hold_reason TEXT,
                    reject_reason TEXT,
                    risk_notes_json TEXT,
                    suggested_next_action TEXT,
                    raw_agent_output TEXT NOT NULL,
                    source_data_json TEXT, -- 원본 소스 데이터 (mapped_input) 스냅샷
                    latest_revision_id TEXT, -- 현재 리비전 ID
                    latest_revision_number INTEGER, -- 현재 리비전 번호
                    latest_registration_status TEXT, -- 현재 상태 (리비전 반영본)
                    latest_registration_title_ko TEXT, -- 현재 제목 (리비전 반영본)
                    reviewer_status TEXT NOT NULL,
                    reviewer_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS revisions (
                    revision_id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    revision_number INTEGER NOT NULL,
                    source_snapshot_json TEXT NOT NULL,
                    previous_agent_output_json TEXT,
                    reviewer_note TEXT,
                    revised_agent_output_json TEXT,
                    generation_status TEXT NOT NULL, -- pending, completed, failed
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (review_id) REFERENCES approval_queue (review_id)
                )
            ''')
            conn.commit()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS handoff_logs (
                    log_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    item_count INTEGER NOT NULL,
                    export_generated BOOLEAN NOT NULL,
                    slack_status TEXT NOT NULL,
                    slack_error TEXT,
                    email_status TEXT NOT NULL,
                    email_error TEXT,
                    mode TEXT NOT NULL
                )
            ''')
            conn.commit()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS handoff_runs (
                    run_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    mode TEXT NOT NULL,
                    item_count INTEGER,
                    slack_status TEXT,
                    email_status TEXT,
                    overall_result TEXT,
                    error_message TEXT
                )
            ''')
            conn.commit()

    def create_item(self, source_type: str, source_title: str, agent_output: Dict[str, Any], source_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Agent의 Dictionary Output(Pydantic model_dump)을 손상 없이 저장합니다.
        """
        review_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        # Extract direct fields for easy indexing/reading
        reg_title = agent_output.get("registration_title_ko")
        reg_status = agent_output.get("registration_status", "unknown")
        human_review = int(agent_output.get("needs_human_review", True))
        hold_reason = agent_output.get("hold_reason")
        reject_reason = agent_output.get("reject_reason")
        risk_notes = json.dumps(agent_output.get("risk_notes", []))
        next_action = agent_output.get("suggested_next_action")
        
        raw_json = json.dumps(agent_output, ensure_ascii=False)
        source_json = json.dumps(source_data, ensure_ascii=False) if source_data else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. approval_queue 에 아이템 삽입 (초기)
            cursor.execute('''
                INSERT INTO approval_queue (
                    review_id, source_type, source_title, registration_title_ko,
                    registration_status, needs_human_review, hold_reason, reject_reason,
                    risk_notes_json, suggested_next_action, raw_agent_output,
                    source_data_json, latest_revision_id, latest_revision_number,
                    latest_registration_status, latest_registration_title_ko,
                    reviewer_status, reviewer_note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                review_id, source_type, source_title, reg_title,
                reg_status, human_review, hold_reason, reject_reason,
                risk_notes, next_action, raw_json,
                source_json, None, 1, reg_status, reg_title,
                "pending", None, now, now
            ))
            
            # 2. Revision 1 (Materialization) 자동 생성
            revision_id = str(uuid.uuid4())
            # Revision 1은 최초 결과를 그대로 반영하므로 revised_agent_output_json에 저장
            cursor.execute('''
                INSERT INTO revisions (
                    revision_id, review_id, revision_number, source_snapshot_json,
                    previous_agent_output_json, revised_agent_output_json, reviewer_note,
                    generation_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                revision_id, review_id, 1, source_json or "{}",
                None, raw_json, "Initial AI Generation (Auto-persisted Revision 1)",
                "completed", now
            ))
            
            # 3. 최신 리비전 ID 업데이트
            cursor.execute('''
                UPDATE approval_queue SET latest_revision_id = ? WHERE review_id = ?
            ''', (revision_id, review_id))
            
            conn.commit()
            
        logger.info(f"✅ Approval Queue item created: {review_id} (Status: {reg_status})")
        return review_id

    def list_items(self, reviewer_status: str = "pending") -> List[Dict[str, Any]]:
        if reviewer_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid reviewer_status: {reviewer_status}")
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM approval_queue WHERE reviewer_status = ? ORDER BY created_at DESC', (reviewer_status,))
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                item = dict(r)
                item['needs_human_review'] = bool(item['needs_human_review'])
                item['risk_notes'] = json.loads(item['risk_notes_json'])
                item['raw_agent_output'] = json.loads(item['raw_agent_output'])
                del item['risk_notes_json']
                results.append(item)
            return results

    def get_item(self, review_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM approval_queue WHERE review_id = ?', (review_id,))
            row = cursor.fetchone()
            
            if row:
                item = dict(row)
                item['needs_human_review'] = bool(item['needs_human_review'])
                item['risk_notes'] = json.loads(item['risk_notes_json'])
                item['raw_agent_output'] = json.loads(item['raw_agent_output'])
                item['source_data'] = json.loads(item['source_data_json']) if item['source_data_json'] else {}
                del item['risk_notes_json']
                del item['source_data_json']
                return item
            return None

    def update_reviewer_status(self, review_id: str, new_status: str, note: Optional[str] = None):
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid reviewer_status: {new_status}")
            
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE approval_queue 
                SET reviewer_status = ?, reviewer_note = ?, updated_at = ?
                WHERE review_id = ?
            ''', (new_status, note, now, review_id))
            
            if cursor.rowcount == 0:
                raise KeyError(f"Review item {review_id} not found")
            conn.commit()
        logger.info(f"✅ Review {review_id} updated: {new_status}")

    def get_latest_revision(self, review_id: str) -> Optional[Dict[str, Any]]:
        """가장 최신(높은 revision_number)의 리비전을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM revisions 
                WHERE review_id = ? 
                ORDER BY revision_number DESC LIMIT 1
            ''', (review_id,))
            row = cursor.fetchone()
            if row:
                item = dict(row)
                if item['revised_agent_output_json']:
                    item['revised_agent_output'] = json.loads(item['revised_agent_output_json'])
                return item
            return None

    def list_revisions(self, review_id: str) -> List[Dict[str, Any]]:
        """특정 리뷰 아이템의 전체 리비전 이력을 조회합니다."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM revisions 
                WHERE review_id = ? 
                ORDER BY revision_number ASC
            ''', (review_id,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                if item['revised_agent_output_json']:
                    item['revised_agent_output'] = json.loads(item['revised_agent_output_json'])
                results.append(item)
            return results

    def get_latest_approved_items(self) -> List[Dict[str, Any]]:
        """
        'approved' 상태인 모든 아이템의 최신 리비전을 교차 검증하여 조회합니다.
        가장 최근 승인된 리비전(Latest)만 추출합니다.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # latest_revision_id를 기준으로 revisions 테이블과 join하여 최신 데이터만 추출
            cursor.execute('''
                SELECT q.*, r.revised_agent_output_json, r.revision_id, r.revision_number
                FROM approval_queue q
                JOIN revisions r ON q.latest_revision_id = r.revision_id
                WHERE q.reviewer_status = 'approved'
                ORDER BY q.updated_at DESC
            ''')
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                item = dict(r)
                if item['revised_agent_output_json']:
                    item['revised_agent_output'] = json.loads(item['revised_agent_output_json'])
                item['raw_agent_output'] = json.loads(item['raw_agent_output'])
                item['source_data'] = json.loads(item['source_data_json']) if item['source_data_json'] else {}
                results.append(item)
            return results

    def create_revision_pending(self, review_id: str, source_snapshot: Dict[str, Any], previous_output: Dict[str, Any], reviewer_note: str) -> str:
        """새로운 리비전을 'pending' 상태로 생성합니다. 중복 방지를 위해 기존 pending 유무를 확인해야 합니다."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # 1. 중복 pending 확인
            cursor.execute('SELECT 1 FROM revisions WHERE review_id = ? AND generation_status = "pending"', (review_id,))
            if cursor.fetchone():
                raise ConnectionError("이미 처리 중인 Revision(Retry)이 존재합니다.")
            
            # 2. 다음 revision_number 결정
            cursor.execute('SELECT MAX(revision_number) FROM revisions WHERE review_id = ?', (review_id,))
            max_rev = cursor.fetchone()[0]
            next_rev = (max_rev or 1) + 1 # 최초 결과물은 Revision 1로 간주하므로 2부터 시작
            
            revision_id = str(uuid.uuid4())
            now = datetime.utcnow().isoformat()
            
            cursor.execute('''
                INSERT INTO revisions (
                    revision_id, review_id, revision_number, source_snapshot_json,
                    previous_agent_output_json, reviewer_note, generation_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                revision_id, review_id, next_rev, json.dumps(source_snapshot, ensure_ascii=False),
                json.dumps(previous_output, ensure_ascii=False), reviewer_note, "pending", now
            ))
            conn.commit()
            return revision_id

    def complete_revision(self, revision_id: str, revised_output: Optional[Dict[str, Any]], status: str):
        """리비전 생성을 완료(success/failed)하고 결과를 반영합니다."""
        if status not in ["completed", "failed"]:
            raise ValueError("Status must be completed or failed")
            
        now = datetime.utcnow().isoformat()
        revised_json = json.dumps(revised_output, ensure_ascii=False) if revised_output else None
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE revisions 
                SET revised_agent_output_json = ?, generation_status = ?, created_at = ?
                WHERE revision_id = ?
            ''', (revised_json, status, now, revision_id))
            
            # review_id를 찾아서 main queue의 검색용 필드 업데이트
            if status == "completed" and revised_output:
                cursor.execute('SELECT review_id, revision_number FROM revisions WHERE revision_id = ?', (revision_id,))
                rid_row = cursor.fetchone()
                if rid_row:
                    review_id, next_rev = rid_row[0], rid_row[1]
                    reg_title = revised_output.get("registration_title_ko")
                    reg_status = revised_output.get("registration_status")
                    human_review = int(revised_output.get("needs_human_review", True))
                    hold_reason = revised_output.get("hold_reason")
                    reject_reason = revised_output.get("reject_reason")
                    risk_notes = json.dumps(revised_output.get("risk_notes", []))
                    
                    cursor.execute('''
                        UPDATE approval_queue
                        SET registration_title_ko = ?, registration_status = ?,
                            needs_human_review = ?, hold_reason = ?,
                            reject_reason = ?, risk_notes_json = ?,
                            latest_revision_id = ?, latest_revision_number = ?,
                            latest_registration_status = ?, latest_registration_title_ko = ?,
                            reviewer_status = "pending", updated_at = ?
                        WHERE review_id = ?
                    ''', (
                        reg_title, reg_status, human_review, hold_reason,
                        reject_reason, risk_notes, revision_id, next_rev,
                        reg_status, reg_title, now, review_id
                    ))
            conn.commit()

    def create_handoff_log(self, item_count: int, export_generated: bool, 
                           slack_status: str, slack_error: Optional[str],
                           email_status: str, email_error: Optional[str],
                           mode: str) -> str:
        log_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO handoff_logs (
                    log_id, timestamp, item_count, export_generated,
                    slack_status, slack_error, email_status, email_error, mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                log_id, now, item_count, int(export_generated),
                slack_status, slack_error, email_status, email_error, mode
            ))
            conn.commit()
        return log_id

    def get_handoff_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM handoff_logs ORDER BY timestamp DESC LIMIT ?', (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def start_handoff_run(self, mode: str) -> str:
        """Start a new handoff run. Returns run_id if successful, raises HTTPException if already running."""
        run_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check for existing running handoff
            cursor.execute('''
                SELECT run_id, started_at FROM handoff_runs
                WHERE status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
            ''')
            existing = cursor.fetchone()

            if existing:
                existing_run_id, started_at = existing
                # Stale lock detection: if running for more than 10 minutes, allow override
                started = datetime.fromisoformat(started_at)
                elapsed = (datetime.utcnow() - started).total_seconds()

                if elapsed < 600:  # 10 minutes
                    from fastapi import HTTPException
                    raise HTTPException(
                        status_code=409,
                        detail=f"Handoff already in progress (run_id: {existing_run_id}, started: {started_at}). Please wait or reset manually."
                    )
                else:
                    # Stale lock detected, mark as failed and allow new run
                    cursor.execute('''
                        UPDATE handoff_runs
                        SET status = 'failed', finished_at = ?, error_message = ?
                        WHERE run_id = ?
                    ''', (now, 'Stale lock detected (>10 min), auto-failed', existing_run_id))

            # Create new run
            cursor.execute('''
                INSERT INTO handoff_runs (
                    run_id, status, started_at, mode
                ) VALUES (?, ?, ?, ?)
            ''', (run_id, 'running', now, mode))
            conn.commit()

        return run_id

    def finish_handoff_run(self, run_id: str, status: str, item_count: int,
                          slack_status: str, email_status: str, overall_result: str,
                          error_message: Optional[str] = None):
        """Mark handoff run as completed or failed."""
        now = datetime.utcnow().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE handoff_runs
                SET status = ?, finished_at = ?, item_count = ?,
                    slack_status = ?, email_status = ?, overall_result = ?,
                    error_message = ?
                WHERE run_id = ?
            ''', (status, now, item_count, slack_status, email_status,
                  overall_result, error_message, run_id))
            conn.commit()

    def get_current_handoff_run(self) -> Optional[Dict[str, Any]]:
        """Get currently running handoff, if any."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM handoff_runs
                WHERE status = 'running'
                ORDER BY started_at DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_handoff_run_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent handoff runs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM handoff_runs
                ORDER BY started_at DESC
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def validate_reviewer_note(note: str) -> Optional[str]:
        """
        리뷰어의 수정 요청 사항(note)을 검증합니다.
        문제가 있을 경우 에러 메시지를 반환하고, 정상이면 None을 반환합니다.
        """
        if not note or not note.strip():
            return "메모가 비어 있습니다."
        
        note_clean = note.strip()
        if len(note_clean) < 5:
            return "메모가 너무 짧습니다. 최소 5자 이상 입력해 주세요. (예: '제목에서 브랜드 삭제')"
        
        # 모호 표현 블랙리스트
        blacklist = ["다시", "수정", "잘 좀 해봐", "이상함", "알아서", "단순", "대충", "바꿔"]
        # 블랙리스트에만 완전히 매칭되거나, 블랙리스트 단어만 포함된 경우 차단
        if any(bad in note_clean for bad in blacklist) and len(note_clean) < 10:
             # 짧으면서 블랙리스트 단어가 포함된 경우 (예: "다시 수정해", "잘 좀 해봐")
             return f"모호한 표현('{note_clean}')이 포함되어 있습니다. 어떤 부분을 어떻게 수정할지 구체적으로 적어주세요."

        # Bounded Correction 여부 (간단한 키워드 힌트 확인)
        targets = ["제목", "옵션", "설명", "브랜드", "문구", "표현", "가격", "삭제", "추가", "정리"]
        if not any(t in note_clean for t in targets):
            if len(note_clean) < 15: # 충분히 길지 않으면서 타겟 키워드도 없는 경우 경고형 실패
                return "무엇을 수정해야 할지 명확하지 않습니다. (예: '제목', '설명', '브랜드' 등 대상 명시)"

        return None
