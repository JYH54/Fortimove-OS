"""
Korean Law MCP 헬퍼 클래스
- Korean Law MCP 서버 연동 (HTTP/Subprocess 이중 지원)
- 의료기기법, 약사법, 관세법, 건강기능식품법 등 법령 검색
- 상품 법적 리스크 판단 지원
"""

import os
import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# MCP 서버 기본 설정
DEFAULT_MCP_HTTP_URL = "http://127.0.0.1:8200/mcp"
DEFAULT_MCP_PATH = Path(__file__).resolve().parent.parent / "korean-law-mcp"


class KoreanLawMCPClient:
    """Korean Law MCP HTTP 클라이언트"""

    def __init__(self, base_url: str = DEFAULT_MCP_HTTP_URL):
        self.base_url = base_url
        self.session_id: Optional[str] = None

    def _ensure_session(self) -> str:
        """MCP 세션 초기화 (initialize 호출)"""
        if self.session_id:
            return self.session_id

        import urllib.request

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "pm-agent", "version": "1.0.0"}
            }
        }

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.session_id = resp.headers.get("mcp-session-id")
                return self.session_id or ""
        except Exception as e:
            logger.error(f"MCP session init failed: {e}")
            return ""

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """MCP 도구 호출"""
        import urllib.request

        session_id = self._ensure_session()

        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }

        headers = {"Content-Type": "application/json"}
        if session_id:
            headers["mcp-session-id"] = session_id

        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if "result" in result:
                    content = result["result"].get("content", [])
                    texts = [c.get("text", "") for c in content if c.get("type") == "text"]
                    return "\n".join(texts)
                elif "error" in result:
                    logger.error(f"MCP tool error: {result['error']}")
                    return None
        except Exception as e:
            logger.error(f"MCP call_tool({tool_name}) failed: {e}")
            return None


class KoreanLawHelper:
    """Korean Law MCP를 사용한 법령 검색 헬퍼 (HTTP 우선, subprocess 폴백)"""

    def __init__(self):
        self.law_oc = os.getenv("LAW_OC", "")
        self.mcp_url = os.getenv("LAW_MCP_URL", DEFAULT_MCP_HTTP_URL)
        self.mcp_path = Path(os.getenv("LAW_MCP_PATH", str(DEFAULT_MCP_PATH)))
        self.mcp_client = KoreanLawMCPClient(self.mcp_url)

        # HTTP 연결 가능 여부 체크
        self.http_available = self._check_http()

        # HTTP 안 되면 subprocess 폴백
        build_index = self.mcp_path / "build" / "index.js"
        self.subprocess_available = build_index.exists()

        self.available = self.http_available or self.subprocess_available

        if self.http_available:
            logger.info(f"Korean Law MCP connected via HTTP: {self.mcp_url}")
        elif self.subprocess_available:
            logger.info(f"Korean Law MCP available via subprocess: {self.mcp_path}")
        else:
            logger.warning("Korean Law MCP not available (HTTP/subprocess both failed)")

    def _check_http(self) -> bool:
        """HTTP MCP 서버 접속 가능 여부 확인"""
        import urllib.request
        try:
            req = urllib.request.Request(self.mcp_url, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                pass
            return True
        except Exception:
            return False

    def _call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """MCP 도구 호출 (HTTP 우선 → subprocess 폴백)"""
        # HTTP 시도
        if self.http_available:
            result = self.mcp_client.call_tool(tool_name, arguments)
            if result is not None:
                return result

        # Subprocess 폴백 (CLI 모드)
        if self.subprocess_available:
            return self._call_via_subprocess(tool_name, arguments)

        return None

    def _call_via_subprocess(self, tool_name: str, arguments: Dict[str, Any]) -> Optional[str]:
        """Subprocess CLI를 통한 MCP 도구 호출"""
        try:
            cmd = ["node", str(self.mcp_path / "build" / "cli.js")]

            # CLI 명령어 구성
            if tool_name == "search_law":
                cmd.extend([tool_name, "--query", arguments.get("query", "")])
            elif tool_name == "get_law_text":
                cmd.extend([tool_name, "--mst", str(arguments.get("mst", ""))])
                if "jo" in arguments:
                    cmd.extend(["--jo", arguments["jo"]])
            elif tool_name == "search_all":
                cmd.extend([tool_name, "--query", arguments.get("query", "")])
            else:
                cmd.extend([tool_name])
                for k, v in arguments.items():
                    cmd.extend([f"--{k}", str(v)])

            env = os.environ.copy()
            if self.law_oc:
                env["LAW_OC"] = self.law_oc

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=15, env=env, cwd=str(self.mcp_path)
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()

            logger.error(f"CLI call failed: {result.stderr}")
            return None

        except subprocess.TimeoutExpired:
            logger.error(f"CLI timeout: {tool_name}")
            return None
        except Exception as e:
            logger.error(f"CLI error: {e}")
            return None

    # ============================================================
    # 법령 검색 API
    # ============================================================

    def search_law(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """법령 키워드 검색"""
        if not self.available:
            return []

        result = self._call_mcp_tool("search_law", {"query": keyword, "display": limit})
        if not result:
            return []

        try:
            return json.loads(result) if result.startswith("[") else [{"text": result}]
        except json.JSONDecodeError:
            return [{"text": result}]

    def search_all(self, keyword: str) -> Optional[str]:
        """법령+행정규칙+자치법규 통합검색"""
        return self._call_mcp_tool("search_all", {"query": keyword})

    def get_law_text(self, mst: str, jo: Optional[str] = None) -> Optional[str]:
        """법령 조문 조회"""
        args: Dict[str, Any] = {"mst": mst}
        if jo:
            args["jo"] = jo
        return self._call_mcp_tool("get_law_text", args)

    # ============================================================
    # 컴플라이언스 체크 (소싱 에이전트 연동)
    # ============================================================

    # 리스크 키워드 사전
    MEDICAL_DEVICE_KEYWORDS = [
        "치료", "완치", "혈압", "혈당", "진단", "전기자극", "저주파",
        "의료기기", "체온계", "혈압계", "맥박", "심전도", "초음파",
        "레이저", "적외선", "자외선살균", "산소발생기"
    ]

    PHARMACEUTICAL_KEYWORDS = [
        "의약품", "다이어트약", "수면제", "진통제", "식욕억제", "지방분해",
        "스테로이드", "항생제", "호르몬제", "발모제", "미녹시딜"
    ]

    HEALTH_FOOD_KEYWORDS = [
        "건강기능식품", "혈당조절", "체지방감소", "면역력", "항산화",
        "프로바이오틱스", "콜라겐", "루테인", "오메가3"
    ]

    CUSTOMS_RISK_KEYWORDS = [
        "KC인증", "전파인증", "안전인증", "전기용품", "어린이제품",
        "화장품", "식품", "건강기능", "의약외품"
    ]

    def check_medical_device_law(self, product_name: str, description: str) -> Dict[str, Any]:
        """의료기기법 위반 여부 확인"""
        combined_text = f"{product_name} {description}"
        matched = [kw for kw in self.MEDICAL_DEVICE_KEYWORDS if kw in combined_text]

        if not matched:
            return {"is_violation": False, "law_articles": [], "reason": "의료기기 관련 키워드 미감지"}

        # MCP로 실제 법령 조회 시도
        law_result = self._call_mcp_tool("search_law", {"query": "의료기기법"})
        law_articles = []
        if law_result:
            law_articles.append(f"[법령 검색 결과] {law_result[:500]}")

        return {
            "is_violation": True,
            "matched_keywords": matched,
            "law_articles": law_articles or ["의료기기법 제6조 (제조업 및 수입업 허가 등)"],
            "reason": f"의료기기 관련 키워드 감지: {', '.join(matched)}. 의료기기법 위반 가능성. [확인 필요]"
        }

    def check_pharmaceutical_law(self, product_name: str, description: str) -> Dict[str, Any]:
        """약사법 위반 여부 확인"""
        combined_text = f"{product_name} {description}"
        matched = [kw for kw in self.PHARMACEUTICAL_KEYWORDS if kw in combined_text]

        if not matched:
            return {"is_violation": False, "law_articles": [], "reason": "의약품 관련 키워드 미감지"}

        law_result = self._call_mcp_tool("search_law", {"query": "약사법 의약품 판매"})
        law_articles = []
        if law_result:
            law_articles.append(f"[법령 검색 결과] {law_result[:500]}")

        return {
            "is_violation": True,
            "matched_keywords": matched,
            "law_articles": law_articles or ["약사법 제44조 (의약품의 판매 등 제한)"],
            "reason": f"의약품 관련 키워드 감지: {', '.join(matched)}. 약사법 위반 가능성. [확인 필요]"
        }

    def check_health_food_law(self, product_name: str, description: str) -> Dict[str, Any]:
        """건강기능식품법 위반 여부 확인"""
        combined_text = f"{product_name} {description}"
        matched = [kw for kw in self.HEALTH_FOOD_KEYWORDS if kw in combined_text]

        if not matched:
            return {"is_violation": False, "law_articles": [], "reason": "건강기능식품 관련 키워드 미감지"}

        law_result = self._call_mcp_tool("search_law", {"query": "건강기능식품에 관한 법률"})
        law_articles = []
        if law_result:
            law_articles.append(f"[법령 검색 결과] {law_result[:500]}")

        return {
            "is_violation": True,
            "matched_keywords": matched,
            "law_articles": law_articles or ["건강기능식품에 관한 법률 제18조 (영업의 등록)"],
            "reason": f"건강기능식품 관련 키워드 감지: {', '.join(matched)}. 건강기능식품법 위반 가능성. [확인 필요]"
        }

    def check_customs_risk(self, product_name: str, description: str) -> Dict[str, Any]:
        """통관/인증 리스크 확인"""
        combined_text = f"{product_name} {description}"
        matched = [kw for kw in self.CUSTOMS_RISK_KEYWORDS if kw in combined_text]

        if not matched:
            return {"has_risk": False, "certifications_needed": [], "reason": "통관 리스크 키워드 미감지"}

        return {
            "has_risk": True,
            "matched_keywords": matched,
            "certifications_needed": matched,
            "reason": f"통관/인증 리스크 키워드 감지: {', '.join(matched)}. 수입 시 인증 요건 확인 필수. [확인 필요]"
        }

    def comprehensive_legal_check(self, product_name: str, description: str) -> Dict[str, Any]:
        """상품 종합 법적 리스크 체크 (소싱 에이전트 메인 진입점)"""
        results = {
            "product_name": product_name,
            "medical_device": self.check_medical_device_law(product_name, description),
            "pharmaceutical": self.check_pharmaceutical_law(product_name, description),
            "health_food": self.check_health_food_law(product_name, description),
            "customs": self.check_customs_risk(product_name, description),
            "overall_risk_level": "low",
            "recommendations": []
        }

        # 전체 리스크 수준 결정
        violations = []
        if results["medical_device"].get("is_violation"):
            violations.append("의료기기")
            results["recommendations"].append(self.get_law_recommendation("의료기기"))
        if results["pharmaceutical"].get("is_violation"):
            violations.append("의약품")
            results["recommendations"].append(self.get_law_recommendation("의약품"))
        if results["health_food"].get("is_violation"):
            violations.append("건강기능식품")
            results["recommendations"].append(self.get_law_recommendation("건강기능식품"))
        if results["customs"].get("has_risk"):
            violations.append("통관/인증")

        if len(violations) >= 2:
            results["overall_risk_level"] = "critical"
        elif len(violations) == 1:
            results["overall_risk_level"] = "high"
        elif results["customs"].get("has_risk"):
            results["overall_risk_level"] = "medium"

        results["flagged_categories"] = violations
        return results

    def get_law_recommendation(self, risk_type: str) -> str:
        """리스크 타입별 법률 권고사항 반환"""
        recommendations = {
            "의료기기": """의료기기법 위반 가능성이 있습니다.

[필수 확인 사항]
1. 식품의약품안전처 의료기기 품목허가 여부
2. 제조업/수입업 신고 여부
3. 의료기기 등급 분류 (1등급~4등급)

[법적 근거]
- 의료기기법 제6조 (제조업 및 수입업 허가 등)
- 처벌: 5년 이하 징역 또는 5천만원 이하 벌금

[권고사항]
→ 이 상품은 소싱하지 마십시오. 법률 자문 필수.""",

            "의약품": """약사법 위반 가능성이 있습니다.

[필수 확인 사항]
1. 의약품 수입 허가 여부
2. 약국 또는 의약품 판매업 허가 여부
3. 한약재 수입 요건 충족 여부

[법적 근거]
- 약사법 제44조 (의약품의 판매 등 제한)
- 처벌: 10년 이하 징역 또는 1억원 이하 벌금

[권고사항]
→ 이 상품은 소싱하지 마십시오. 법률 자문 필수.""",

            "건강기능식품": """건강기능식품법 위반 가능성이 있습니다.

[필수 확인 사항]
1. 건강기능식품 영업 등록 여부
2. 기능성 원료 인정 여부 (식약처)
3. 수입 건강기능식품 신고 여부

[법적 근거]
- 건강기능식품에 관한 법률 제18조 (영업의 등록)
- 처벌: 5년 이하 징역 또는 5천만원 이하 벌금

[권고사항]
→ 건강기능식품 표방 불가. 일반식품으로 등록 시 기능성 표현 삭제 필수. [확인 필요]"""
        }

        return recommendations.get(risk_type, f"알 수 없는 리스크 타입: {risk_type}")


# 글로벌 인스턴스 (싱글톤)
_korean_law_helper = None

def get_korean_law_helper() -> KoreanLawHelper:
    """Korean Law Helper 싱글톤 인스턴스 반환"""
    global _korean_law_helper
    if _korean_law_helper is None:
        _korean_law_helper = KoreanLawHelper()
    return _korean_law_helper
