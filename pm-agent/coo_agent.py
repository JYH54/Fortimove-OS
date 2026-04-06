"""
COO Agent — 경영 판단 레이어

역할:
- 전체 시스템 데이터를 종합 분석하여 CEO에게 액션을 제안
- 위닝 상품 판별, 마진 경고, 브랜드 전환 후보, 경쟁 모니터링
- 주간/월간 브리핑 자동 생성
- 실행하지 않고 판단만 함 (실행은 하위 에이전트)

데이터 소스:
- approval_queue (상품 큐, 점수, 상태)
- scoring_engine (점수 분석)
- wellness_products (Daily Scout 트렌드)
- audit_log (워크플로우 추적)
- redesign_queue (상세페이지 파이프라인)
- pricing (마진/원가)
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DB_PATH = str(Path(__file__).parent / "data" / "approval_queue.db")


class COOAgent:
    """COO 경영 판단 에이전트"""

    def __init__(self):
        self.db_path = DB_PATH
        self._llm = None

    def _call_llm(self, prompt: str, task_type: str = "risk_analysis") -> str:
        """Claude로 분석 (추론 정확도 필수 → Claude 라우팅)"""
        try:
            from llm_router import call_llm
            return call_llm(task_type=task_type, prompt=prompt, max_tokens=4096)
        except Exception as e:
            logger.error(f"LLM 호출 실패: {e}")
            return ""

    def _query(self, sql: str, params: tuple = ()) -> List[Dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # ── 1. 전체 현황 스냅샷 ───────────────────────────────

    def get_system_snapshot(self) -> Dict[str, Any]:
        """시스템 전체 현황 스냅샷"""
        # 큐 상태
        queue_stats = self._query("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN reviewer_status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN reviewer_status='approved' THEN 1 ELSE 0 END) as approved,
                SUM(CASE WHEN reviewer_status='rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN reviewer_status='needs_edit' THEN 1 ELSE 0 END) as needs_edit
            FROM approval_queue
        """)

        # 점수 분포
        score_dist = self._query("""
            SELECT
                CASE
                    WHEN score >= 80 THEN 'auto_approve (80+)'
                    WHEN score >= 60 THEN 'review (60-79)'
                    WHEN score >= 40 THEN 'hold (40-59)'
                    ELSE 'reject (<40)'
                END as tier,
                COUNT(*) as count,
                ROUND(AVG(score), 1) as avg_score
            FROM approval_queue WHERE score IS NOT NULL
            GROUP BY tier ORDER BY avg_score DESC
        """)

        # 최근 7일 처리량
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        daily_volume = self._query("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM approval_queue WHERE created_at >= ?
            GROUP BY DATE(created_at) ORDER BY date
        """, (seven_days_ago,))

        # 마진 분석 (raw_agent_output에서 추출 — score 없어도 마진 데이터 있으면 표시)
        margin_data = self._query("""
            SELECT review_id, source_title, raw_agent_output, score, created_at
            FROM approval_queue
            WHERE raw_agent_output IS NOT NULL
            ORDER BY created_at DESC LIMIT 30
        """)

        margins = []
        for item in margin_data:
            try:
                output = json.loads(item["raw_agent_output"]) if isinstance(item["raw_agent_output"], str) else (item["raw_agent_output"] or {})
                # raw_agent_output에 margin_analysis가 직접 있음
                ma = output.get("margin_analysis", {})
                cb = output.get("cost_breakdown", {})
                if ma or cb:
                    margins.append({
                        "title": item["source_title"],
                        "score": item["score"],
                        "margin_rate": ma.get("net_margin_rate", 0),
                        "final_price": ma.get("target_price", 0),
                        "margin_amount": ma.get("net_profit", 0),
                        "total_cost": cb.get("total_cost_krw", 0),
                        "decision": output.get("final_decision", ""),
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        # 리디자인 큐
        redesign_stats = self._query("""
            SELECT status, COUNT(*) as count
            FROM redesign_queue
            GROUP BY status
        """)

        return {
            "timestamp": datetime.now().isoformat(),
            "queue": queue_stats[0] if queue_stats else {},
            "score_distribution": score_dist,
            "daily_volume_7d": daily_volume,
            "top_margin_products": sorted(margins, key=lambda x: x.get("margin_rate", 0), reverse=True)[:10],
            "redesign_status": {r["status"]: r["count"] for r in redesign_stats},
        }

    # ── 2. 위닝 상품 판별 ─────────────────────────────────

    def identify_winning_products(self) -> Dict[str, Any]:
        """위닝 상품 후보 식별 — 고득점 상품 (reviewer_status 무관)"""
        candidates = self._query("""
            SELECT review_id, source_title, generated_naver_title, score, decision, raw_agent_output, created_at
            FROM approval_queue
            WHERE score >= 70
            ORDER BY score DESC LIMIT 20
        """)

        # 무효 상품명 패턴 (정확 매칭 또는 포함 검사)
        bad_exact = {'按图片搜索', 'Unknown Product', '无效'}
        bad_contains = ['按图片', 'search ui']  # 부분 포함 금지

        def is_bad_title(t: str) -> bool:
            if not t or len(t.strip()) < 5:
                return True
            t_stripped = t.strip()
            if t_stripped in bad_exact:
                return True
            t_lower = t_stripped.lower()
            return any(b in t_lower for b in bad_contains)

        winners = []
        for c in candidates:
            src_title = c["source_title"] or ""
            gen_title = c["generated_naver_title"] or ""

            # 무효 상품명 스킵 (둘 다 무효면 스킵)
            if is_bad_title(src_title) and is_bad_title(gen_title):
                continue

            # 실제 표시할 제목 (generated_naver_title 우선)
            display_title = gen_title if gen_title and len(gen_title) > 10 else src_title

            try:
                output = json.loads(c["raw_agent_output"]) if isinstance(c["raw_agent_output"], str) else (c["raw_agent_output"] or {})
                ma = output.get("margin_analysis", {})

                winners.append({
                    "review_id": c["review_id"],
                    "title": display_title,
                    "score": c["score"],
                    "margin_rate": ma.get("net_margin_rate", 0),
                    "final_price": ma.get("target_price", 0),
                    "decision": output.get("final_decision", ""),
                    "risk_warnings": output.get("risk_warnings", []),
                })
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "total_candidates": len(winners),
            "winners": winners,
            "analysis_date": datetime.now().isoformat(),
        }

    # ── 3. 마진 경고 ──────────────────────────────────────

    def margin_alerts(self) -> List[Dict[str, Any]]:
        """마진 위험 상품 경고"""
        items = self._query("""
            SELECT review_id, source_title, score, raw_agent_output
            FROM approval_queue
            WHERE raw_agent_output IS NOT NULL AND score IS NOT NULL
            ORDER BY created_at DESC LIMIT 50
        """)

        alerts = []
        for item in items:
            try:
                output = json.loads(item["raw_agent_output"]) if isinstance(item["raw_agent_output"], str) else (item["raw_agent_output"] or {})
                ma = output.get("margin_analysis", {})

                if not ma:
                    alerts.append({
                        "level": "info",
                        "title": item["source_title"],
                        "margin_rate": None,
                        "final_price": 0,
                        "message": "마진 데이터 미수집 — 소싱 검증 필요",
                    })
                    continue

                margin_rate = ma.get("net_margin_rate", 0)
                if margin_rate < 15:
                    alerts.append({
                        "level": "critical" if margin_rate < 5 else "warning",
                        "title": item["source_title"],
                        "margin_rate": margin_rate,
                        "final_price": ma.get("target_price", 0),
                        "message": f"마진율 {margin_rate}% — {'적자 위험' if margin_rate < 5 else '저마진 경고'}",
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        return sorted(alerts, key=lambda x: (
            {"critical": 0, "warning": 1, "info": 2}.get(x.get("level", "info"), 2),
            x.get("margin_rate") or 999
        ))

    # ── 4. PB 전환 후보 판별 ──────────────────────────────

    def pb_candidates(self) -> List[Dict[str, Any]]:
        """Fortimove PB 브랜드 전환 후보 (3단계 조건)"""
        # 3단계 조건: score 85+, margin 40%+, 반복 판매 데이터 (현재는 score로 대리)
        items = self._query("""
            SELECT review_id, source_title, score, raw_agent_output, created_at
            FROM approval_queue
            WHERE score >= 85 AND (reviewer_status = 'approved' OR decision = 'auto_approve')
            ORDER BY score DESC
        """)

        candidates = []
        for item in items:
            try:
                output = json.loads(item["raw_agent_output"]) if isinstance(item["raw_agent_output"], str) else (item["raw_agent_output"] or {})
                pricing = output.get("all_results", {}).get("pricing", {})
                sourcing = output.get("all_results", {}).get("sourcing", {})
                margin_rate = pricing.get("margin_rate", 0)

                if margin_rate >= 35:
                    candidates.append({
                        "title": item["source_title"],
                        "score": item["score"],
                        "margin_rate": margin_rate,
                        "risk_flags": len(sourcing.get("risk_flags", [])),
                        "pb_readiness": "높음" if margin_rate >= 45 and item["score"] >= 90 else "보통",
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        return candidates

    # ── 5. 운영 병목 분석 ─────────────────────────────────

    def bottleneck_analysis(self) -> Dict[str, Any]:
        """파이프라인 병목 식별"""
        # 상태별 체류 시간
        stalled = self._query("""
            SELECT review_id, source_title, reviewer_status, score,
                   created_at, updated_at,
                   ROUND(JULIANDAY('now') - JULIANDAY(created_at), 1) as days_in_queue
            FROM approval_queue
            WHERE reviewer_status IN ('pending', 'needs_edit')
            ORDER BY days_in_queue DESC LIMIT 10
        """)

        # 실패 패턴
        failures = self._query("""
            SELECT last_error, COUNT(*) as count
            FROM approval_queue
            WHERE last_error IS NOT NULL AND last_error != ''
            GROUP BY last_error ORDER BY count DESC LIMIT 5
        """)

        # 리트라이 큐
        retries = self._query("""
            SELECT task_type, status, COUNT(*) as count
            FROM retry_queue
            GROUP BY task_type, status
        """)

        return {
            "stalled_items": stalled,
            "top_failure_patterns": failures,
            "retry_queue": retries,
        }

    # ── 6. COO 브리핑 생성 (AI) ───────────────────────────

    def _get_cached_briefing(self, period: str) -> Optional[Dict[str, Any]]:
        """캐시된 브리핑 조회 (1시간 TTL)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS coo_briefing_cache (
                    period TEXT PRIMARY KEY,
                    data_json TEXT,
                    generated_at TEXT
                )''')
                row = conn.execute('SELECT data_json, generated_at FROM coo_briefing_cache WHERE period=?', (period,)).fetchone()
                if row:
                    generated = datetime.fromisoformat(row[1])
                    if (datetime.now() - generated).total_seconds() < 3600:
                        return json.loads(row[0])
        except Exception:
            pass
        return None

    def _save_briefing_cache(self, period: str, data: Dict):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('INSERT OR REPLACE INTO coo_briefing_cache (period, data_json, generated_at) VALUES (?, ?, ?)',
                             (period, json.dumps(data, ensure_ascii=False), datetime.now().isoformat()))
                conn.commit()
        except Exception:
            pass

    def generate_briefing(self, period: str = "daily") -> Dict[str, Any]:
        """AI 기반 COO 브리핑 생성 (1시간 캐싱)"""
        # 캐시 확인
        cached = self._get_cached_briefing(period)
        if cached:
            return cached

        snapshot = self.get_system_snapshot()
        winners = self.identify_winning_products()
        alerts = self.margin_alerts()
        pb = self.pb_candidates()
        bottlenecks = self.bottleneck_analysis()

        # AI에게 종합 분석 요청
        data_summary = json.dumps({
            "queue_status": snapshot["queue"],
            "score_distribution": snapshot["score_distribution"],
            "daily_volume": snapshot["daily_volume_7d"],
            "top_margin": snapshot["top_margin_products"][:5],
            "winning_count": winners["total_candidates"],
            "margin_alerts_count": len(alerts),
            "critical_alerts": [a for a in alerts if a["level"] == "critical"][:3],
            "pb_candidates_count": len(pb),
            "stalled_items_count": len(bottlenecks["stalled_items"]),
        }, ensure_ascii=False, indent=2)

        prompt = f"""당신은 Fortimove의 COO(최고운영책임자)입니다.
CEO에게 보고할 {period} 브리핑을 작성하세요.

## 시스템 데이터
{data_summary}

## 브리핑 형식 (JSON)
{{
  "headline": "오늘의 핵심 한 줄 (예: '마진 경고 2건, 위닝 후보 3건 발견')",
  "status_summary": "전체 현황 2-3줄 요약",
  "action_items": [
    {{"priority": "P0/P1/P2", "action": "구체적 실행 제안", "reason": "판단 근거"}}
  ],
  "winning_products": ["위닝 상품 제목 목록"],
  "risk_alerts": ["리스크 경고 메시지"],
  "pb_recommendation": "PB 전환 추천 (있으면)",
  "bottleneck_note": "병목 사항 (있으면)",
  "next_focus": "다음에 집중해야 할 것"
}}

원칙:
- 단정 금지. 제안만 하고 최종 결정은 CEO에게
- 숫자 근거 필수
- 리스크는 보수적으로 판단
- [확인 필요] 태그 적극 사용

JSON만 반환하세요."""

        try:
            response = self._call_llm(prompt, task_type="risk_analysis")
            # JSON 파싱
            raw = response.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            briefing = json.loads(raw)
        except Exception as e:
            logger.error(f"브리핑 생성 실패: {e}")
            briefing = {
                "headline": f"시스템 요약: 큐 {snapshot['queue'].get('total', 0)}건, 경고 {len(alerts)}건",
                "status_summary": "AI 브리핑 생성 실패. 수동 확인 필요.",
                "action_items": [],
                "risk_alerts": [a["message"] for a in alerts[:3]],
            }

        result = {
            "period": period,
            "generated_at": datetime.now().isoformat(),
            "briefing": briefing,
            "raw_data": {
                "snapshot": snapshot,
                "winners": winners,
                "alerts": alerts,
                "pb_candidates": pb,
                "bottlenecks": bottlenecks,
            },
        }
        self._save_briefing_cache(period, result)
        return result


    # ── 7. 매출 트래킹 ─────────────────────────────────────

    def get_sales_summary(self, days: int = 30) -> Dict[str, Any]:
        """매출 통계 요약"""
        try:
            from sales_tracker import SalesTracker
            tracker = SalesTracker()
            return tracker.get_dashboard_stats(days)
        except Exception as e:
            logger.warning(f"매출 데이터 조회 실패: {e}")
            return {"total": {"order_count": 0, "total_revenue": 0}}

    # ── 8. 경쟁사 모니터링 ────────────────────────────────

    def get_competitor_intel(self) -> Dict[str, Any]:
        """경쟁사 모니터링 리포트"""
        try:
            from competitor_monitor import get_competitor_report
            return get_competitor_report()
        except Exception as e:
            logger.warning(f"경쟁사 모니터링 실패: {e}")
            return {"trademark_alerts": [], "pricing_intelligence": []}

    # ── 9. 주간 리포트 ────────────────────────────────────

    def generate_weekly_report(self) -> Dict[str, Any]:
        """주간 종합 경영 리포트"""
        snapshot = self.get_system_snapshot()
        winners = self.identify_winning_products()
        alerts = self.margin_alerts()
        pb = self.pb_candidates()
        sales = self.get_sales_summary(days=7)
        competitor = self.get_competitor_intel()
        bottlenecks = self.bottleneck_analysis()

        data_summary = json.dumps({
            "queue": snapshot["queue"],
            "score_distribution": snapshot["score_distribution"],
            "winners": winners["total_candidates"],
            "margin_alerts": len(alerts),
            "pb_candidates": len(pb),
            "sales_7d": sales.get("total", {}),
            "top_products": sales.get("top_products", [])[:5],
            "competitor_trademark": competitor.get("summary", {}).get("trademark_count", 0),
            "competitor_pricing": competitor.get("summary", {}).get("pricing_count", 0),
            "stalled": len(bottlenecks.get("stalled_items", [])),
        }, ensure_ascii=False, indent=2)

        prompt = f"""당신은 Fortimove의 COO입니다.
CEO에게 보고할 주간 경영 리포트를 작성하세요.
현재 날짜: {datetime.now().strftime('%Y-%m-%d')}

## 이번 주 데이터
{data_summary}

## 리포트 형식 (JSON)
{{
  "headline": "이번 주 핵심 한 줄",
  "kpi_summary": "KPI 요약 3줄",
  "wins": ["이번 주 잘한 것"],
  "risks": ["주의 필요 사항"],
  "action_items": [{{"priority": "P0/P1/P2", "action": "액션", "deadline": "이번주/다음주"}}],
  "next_week_focus": "다음 주 집중 포인트",
  "competitor_note": "경쟁 동향 한 줄"
}}

JSON만 반환하세요."""

        try:
            response = self._call_llm(prompt, task_type="risk_analysis")
            raw = response.strip()
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()
            report = json.loads(raw)
        except Exception as e:
            logger.error(f"주간 리포트 생성 실패: {e}")
            report = {
                "headline": "주간 리포트 생성 실패 — 수동 확인 필요",
                "kpi_summary": "",
                "action_items": [],
            }

        return {
            "type": "weekly",
            "generated_at": datetime.now().isoformat(),
            "report": report,
            "raw_data": {
                "snapshot": snapshot,
                "sales": sales,
                "competitor": competitor,
            },
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    coo = COOAgent()

    print("=== COO System Snapshot ===")
    snapshot = coo.get_system_snapshot()
    print(json.dumps(snapshot["queue"], ensure_ascii=False, indent=2))
    print(f"\n점수 분포: {snapshot['score_distribution']}")
    print(f"7일 처리량: {snapshot['daily_volume_7d']}")
    print(f"상위 마진 상품: {len(snapshot['top_margin_products'])}개")

    print("\n=== 마진 경고 ===")
    alerts = coo.margin_alerts()
    print(f"경고 건수: {len(alerts)}")
    for a in alerts[:3]:
        print(f"  [{a['level']}] {a['title']}: {a['message']}")

    print("\n=== PB 후보 ===")
    pb = coo.pb_candidates()
    print(f"PB 후보: {len(pb)}개")

    print("\n=== 병목 분석 ===")
    bn = coo.bottleneck_analysis()
    print(f"체류 중: {len(bn['stalled_items'])}건")
