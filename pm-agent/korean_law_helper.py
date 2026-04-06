"""
Korean Law MCP 헬퍼 클래스
- 법제처 API 연동 (Korean Law MCP 사용)
- 의료기기법, 약사법 등 법령 검색
- 상품 법적 리스크 판단 지원
"""

import os
import json
import logging
import subprocess
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class KoreanLawHelper:
    """Korean Law MCP를 사용한 법령 검색 헬퍼"""

    def __init__(self):
        self.law_oc = os.getenv("LAW_OC", "dydgh5942zy")
        self.mcp_path = "/home/fortymove/korean-law-mcp"

        # Korean Law MCP 설치 확인
        if not os.path.exists(os.path.join(self.mcp_path, "build", "index.js")):
            logger.warning(f"Korean Law MCP not found at {self.mcp_path}")
            self.available = False
        else:
            self.available = True
            logger.info("Korean Law MCP helper initialized")

    def search_law(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        법령 검색

        Args:
            keyword: 검색 키워드 (예: "의료기기법 판매")
            limit: 최대 결과 수

        Returns:
            법령 검색 결과 리스트
        """
        if not self.available:
            logger.warning("Korean Law MCP not available, skipping law search")
            return []

        try:
            # Korean Law MCP를 subprocess로 호출
            cmd = [
                "node",
                os.path.join(self.mcp_path, "build", "index.js"),
                "search",
                keyword,
                "--limit", str(limit)
            ]

            env = os.environ.copy()
            env["LAW_OC"] = self.law_oc

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                env=env,
                cwd=self.mcp_path
            )

            if result.returncode == 0:
                # JSON 파싱 시도
                try:
                    output = result.stdout.strip()
                    if output:
                        return json.loads(output)
                except json.JSONDecodeError:
                    # JSON이 아닐 경우 텍스트 결과 반환
                    return [{"text": result.stdout.strip()}]
            else:
                logger.error(f"Korean Law MCP search failed: {result.stderr}")
                return []

        except subprocess.TimeoutExpired:
            logger.error("Korean Law MCP search timeout")
            return []
        except Exception as e:
            logger.error(f"Korean Law MCP search error: {e}")
            return []

    def check_medical_device_law(self, product_name: str, description: str) -> Dict[str, Any]:
        """
        의료기기법 위반 여부 확인

        Args:
            product_name: 상품명
            description: 상품 설명

        Returns:
            {
                "is_violation": bool,
                "law_articles": List[str],
                "reason": str
            }
        """
        # 의료기기 관련 법령 검색
        search_results = self.search_law("의료기기법 제조업 허가")

        if not search_results:
            return {
                "is_violation": None,  # 판단 불가
                "law_articles": [],
                "reason": "법령 검색 결과 없음"
            }

        # 검색 결과에서 위반 여부 판단
        # (간단한 휴리스틱: 의료기기 관련 키워드가 있으면 위반 가능성)
        medical_keywords = ["치료", "완치", "혈압", "혈당", "진단", "전기자극", "저주파"]

        combined_text = f"{product_name} {description}".lower()
        matched = [kw for kw in medical_keywords if kw in combined_text]

        if matched:
            return {
                "is_violation": True,
                "law_articles": ["의료기기법 제6조 (제조업 및 수입업 허가 등)"],
                "reason": f"의료기기 관련 키워드 감지: {', '.join(matched)}. 의료기기법 위반 가능성."
            }
        else:
            return {
                "is_violation": False,
                "law_articles": [],
                "reason": "의료기기 관련 키워드 미감지"
            }

    def check_pharmaceutical_law(self, product_name: str, description: str) -> Dict[str, Any]:
        """
        약사법 위반 여부 확인

        Args:
            product_name: 상품명
            description: 상품 설명

        Returns:
            {
                "is_violation": bool,
                "law_articles": List[str],
                "reason": str
            }
        """
        # 약사법 관련 법령 검색
        search_results = self.search_law("약사법 의약품 판매")

        if not search_results:
            return {
                "is_violation": None,
                "law_articles": [],
                "reason": "법령 검색 결과 없음"
            }

        # 의약품 관련 키워드 감지
        drug_keywords = ["의약품", "다이어트약", "수면제", "진통제", "식욕억제", "지방분해"]

        combined_text = f"{product_name} {description}".lower()
        matched = [kw for kw in drug_keywords if kw in combined_text]

        if matched:
            return {
                "is_violation": True,
                "law_articles": ["약사법 제44조 (의약품의 판매 등 제한)"],
                "reason": f"의약품 관련 키워드 감지: {', '.join(matched)}. 약사법 위반 가능성."
            }
        else:
            return {
                "is_violation": False,
                "law_articles": [],
                "reason": "의약품 관련 키워드 미감지"
            }

    def get_law_recommendation(self, risk_type: str) -> str:
        """
        리스크 타입별 법률 권고사항 반환

        Args:
            risk_type: "의료기기" 또는 "의약품"

        Returns:
            권고사항 텍스트
        """
        if risk_type == "의료기기":
            return """의료기기법 위반 가능성이 있습니다.

[필수 확인 사항]
1. 식품의약품안전처 의료기기 품목허가 여부
2. 제조업/수입업 신고 여부
3. 의료기기 등급 분류 (1등급~4등급)

[법적 근거]
- 의료기기법 제6조 (제조업 및 수입업 허가 등)
- 처벌: 5년 이하 징역 또는 5천만원 이하 벌금

[권고사항]
→ 이 상품은 소싱하지 마십시오. 법률 자문 필수."""

        elif risk_type == "의약품":
            return """약사법 위반 가능성이 있습니다.

[필수 확인 사항]
1. 의약품 수입 허가 여부
2. 약국 또는 의약품 판매업 허가 여부
3. 한약재 수입 요건 충족 여부

[법적 근거]
- 약사법 제44조 (의약품의 판매 등 제한)
- 처벌: 10년 이하 징역 또는 1억원 이하 벌금

[권고사항]
→ 이 상품은 소싱하지 마십시오. 법률 자문 필수."""

        else:
            return f"알 수 없는 리스크 타입: {risk_type}"


# 글로벌 인스턴스 (싱글톤)
_korean_law_helper = None

def get_korean_law_helper() -> KoreanLawHelper:
    """Korean Law Helper 싱글톤 인스턴스 반환"""
    global _korean_law_helper
    if _korean_law_helper is None:
        _korean_law_helper = KoreanLawHelper()
    return _korean_law_helper
