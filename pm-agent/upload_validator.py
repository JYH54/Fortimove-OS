"""
Upload Validator - 채널별 업로드 전 검증
Phase 3 Core Module
"""

import logging
import json
import sqlite3
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class UploadValidator:
    """채널별 업로드 검증 (100% rule-based)"""

    def __init__(self):
        self.db_path = Path(__file__).parent / "data" / "approval_queue.db"
        self._load_validation_rules()

    def _load_validation_rules(self):
        """DB에서 검증 규칙 로드 (hot-reload 지원)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT channel, rule_type, rule_config, severity
                    FROM validation_rules
                    WHERE active = 1
                ''')

                self.rules = {}
                for row in cursor.fetchall():
                    channel = row['channel']
                    if channel not in self.rules:
                        self.rules[channel] = []

                    self.rules[channel].append({
                        "rule_type": row['rule_type'],
                        "config": json.loads(row['rule_config']),
                        "severity": row['severity']
                    })

                logger.info(f"[Validator] Loaded rules for {len(self.rules)} channels")

        except Exception as e:
            logger.error(f"[Validator] Failed to load rules: {e}")
            self.rules = {}

    def validate(
        self,
        channel: str,
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        채널별 콘텐츠 검증

        Args:
            channel: 'naver', 'coupang', 'amazon'
            content: 콘텐츠 데이터

        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "validation_details": Dict
            }
        """
        errors = []
        warnings = []
        validation_details = {}

        channel_rules = self.rules.get(channel, [])

        if not channel_rules:
            logger.warning(f"[Validator] No rules found for channel: {channel}")
            return {
                "valid": True,
                "errors": [],
                "warnings": [f"검증 규칙 없음 ({channel})"],
                "validation_details": {}
            }

        # Apply each rule
        for rule in channel_rules:
            rule_type = rule['rule_type']
            config = rule['config']
            severity = rule['severity']

            result = self._apply_rule(rule_type, config, content)

            if not result['passed']:
                message = result['message']

                if severity == 'error':
                    errors.append(message)
                else:
                    warnings.append(message)

                validation_details[rule_type] = {
                    "passed": False,
                    "message": message,
                    "severity": severity
                }
            else:
                validation_details[rule_type] = {
                    "passed": True,
                    "message": "OK",
                    "severity": severity
                }

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "validation_details": validation_details
        }

    def _apply_rule(
        self,
        rule_type: str,
        config: Dict[str, Any],
        content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """개별 규칙 적용"""

        if rule_type == "title_length":
            return self._validate_title_length(config, content)

        elif rule_type == "prohibited_words":
            return self._validate_prohibited_words(config, content)

        elif rule_type == "price_range":
            return self._validate_price_range(config, content)

        elif rule_type == "option_limit":
            return self._validate_option_limit(config, content)

        elif rule_type == "image_requirement":
            return self._validate_image_requirement(config, content)

        elif rule_type == "required_tag":
            return self._validate_required_tag(config, content)

        elif rule_type == "required_field":
            return self._validate_required_field(config, content)

        else:
            logger.warning(f"[Validator] Unknown rule type: {rule_type}")
            return {"passed": True, "message": "Skipped (unknown rule)"}

    def _validate_title_length(self, config: Dict, content: Dict) -> Dict:
        """제목 길이 검증"""
        title = content.get('title', '')
        max_length = config.get('max', 100)

        if len(title) > max_length:
            return {
                "passed": False,
                "message": f"제목 길이 초과 ({len(title)}/{max_length}자)"
            }

        return {"passed": True, "message": f"제목 길이 OK ({len(title)}자)"}

    def _validate_prohibited_words(self, config: Dict, content: Dict) -> Dict:
        """금지어 검사"""
        prohibited_words = config.get('words', [])
        title = content.get('title', '')
        description = content.get('description', '')

        full_text = f"{title} {description}"

        found_words = []
        for word in prohibited_words:
            if word in full_text:
                found_words.append(word)

        if found_words:
            return {
                "passed": False,
                "message": f"금지어 포함: {', '.join(found_words)}"
            }

        return {"passed": True, "message": "금지어 없음"}

    def _validate_price_range(self, config: Dict, content: Dict) -> Dict:
        """가격 범위 검증"""
        price = content.get('price', 0)
        min_price = config.get('min', 0)
        max_price = config.get('max', 10000000)

        if price < min_price:
            return {
                "passed": False,
                "message": f"최소 가격 미달 ({price}원 < {min_price}원)"
            }

        if price > max_price:
            return {
                "passed": False,
                "message": f"최대 가격 초과 ({price}원 > {max_price}원)"
            }

        return {"passed": True, "message": f"가격 범위 OK ({price}원)"}

    def _validate_option_limit(self, config: Dict, content: Dict) -> Dict:
        """옵션 개수 제한 검증"""
        options = content.get('options', [])
        max_options = config.get('max', 100)

        if len(options) > max_options:
            return {
                "passed": False,
                "message": f"옵션 개수 초과 ({len(options)}/{max_options}개)"
            }

        return {"passed": True, "message": f"옵션 개수 OK ({len(options)}개)"}

    def _validate_image_requirement(self, config: Dict, content: Dict) -> Dict:
        """이미지 요구사항 검증"""
        images = content.get('images', [])
        min_images = config.get('min', 1)
        max_images = config.get('max', 20)

        if len(images) < min_images:
            return {
                "passed": False,
                "message": f"이미지 부족 ({len(images)}/{min_images}장)"
            }

        if len(images) > max_images:
            return {
                "passed": False,
                "message": f"이미지 초과 ({len(images)}/{max_images}장)"
            }

        return {"passed": True, "message": f"이미지 개수 OK ({len(images)}장)"}

    def _validate_required_tag(self, config: Dict, content: Dict) -> Dict:
        """필수 태그 검증 (Coupang 배송 태그 등)"""
        required_tags = config.get('tags', [])
        title = content.get('title', '')

        missing_tags = []
        for tag in required_tags:
            if tag not in title:
                missing_tags.append(tag)

        if missing_tags:
            return {
                "passed": False,
                "message": f"필수 태그 누락: {', '.join(missing_tags)}"
            }

        return {"passed": True, "message": "필수 태그 포함"}

    def _validate_required_field(self, config: Dict, content: Dict) -> Dict:
        """필수 필드 검증"""
        required_fields = config.get('fields', [])

        missing_fields = []
        for field in required_fields:
            if not content.get(field):
                missing_fields.append(field)

        if missing_fields:
            return {
                "passed": False,
                "message": f"필수 필드 누락: {', '.join(missing_fields)}"
            }

        return {"passed": True, "message": "필수 필드 완료"}

    def validate_batch(
        self,
        channel: str,
        content_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """다중 콘텐츠 일괄 검증"""
        results = []

        for content in content_list:
            result = self.validate(channel, content)
            results.append(result)

        return results

    def get_validation_summary(
        self,
        validation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """검증 결과 요약"""
        total = len(validation_results)
        passed = sum(1 for r in validation_results if r['valid'])
        failed = total - passed

        all_errors = []
        all_warnings = []

        for result in validation_results:
            all_errors.extend(result.get('errors', []))
            all_warnings.extend(result.get('warnings', []))

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / total if total > 0 else 0,
            "unique_errors": list(set(all_errors)),
            "unique_warnings": list(set(all_warnings))
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    validator = UploadValidator()

    # Test Naver validation
    naver_content = {
        "title": "프리미엄 스테인리스 텀블러 500ml | 진공 단열",  # 29 chars (OK)
        "description": "고급 스테인리스 소재로 제작된 텀블러입니다.",
        "price": 15900,
        "options": ["300ml", "500ml", "700ml"],
        "images": ["https://example.com/image1.jpg"]
    }

    print("\n=== Naver Validation ===")
    result = validator.validate("naver", naver_content)
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")

    # Test Coupang validation
    coupang_content = {
        "title": "[오늘출발] 프리미엄 텀블러 500ml 진공 단열",  # Has required tag
        "description": "빠른 배송으로 보내드립니다.",
        "price": 15900,
        "options": ["Small", "Medium"],
        "images": ["https://example.com/image1.jpg"],
        "return_policy": "7일 이내 무료 반품"  # Required field
    }

    print("\n=== Coupang Validation ===")
    result = validator.validate("coupang", coupang_content)
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
    print(f"Warnings: {result['warnings']}")

    # Test with prohibited word
    bad_content = {
        "title": "의료기기 인증 FDA 승인 텀블러",  # Prohibited words!
        "description": "치료 효과가 있습니다.",
        "price": 15900,
        "options": [],
        "images": ["https://example.com/image1.jpg"]
    }

    print("\n=== Prohibited Words Test ===")
    result = validator.validate("naver", bad_content)
    print(f"Valid: {result['valid']}")
    print(f"Errors: {result['errors']}")
