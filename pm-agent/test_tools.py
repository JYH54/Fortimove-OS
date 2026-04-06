"""
Fortimove 도구 체인 E2E 테스트
================================
API 키 없이도 실행 가능한 rule-based 기능 테스트

실행: python -m pytest test_tools.py -v
"""

import os
import sys
import json
import tempfile
import pytest

# .env 로드
from pathlib import Path
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)


class TestCountryConfig:
    def test_all_countries_exist(self):
        from country_config import COUNTRIES
        assert "CN" in COUNTRIES
        assert "US" in COUNTRIES
        assert "JP" in COUNTRIES
        assert "VN" in COUNTRIES

    def test_exchange_rates(self):
        from country_config import get_country
        cn = get_country("CN")
        us = get_country("US")
        assert cn.exchange_rate == 195.0
        assert us.exchange_rate == 1380.0
        assert us.currency == "USD"

    def test_url_detection(self):
        from country_config import detect_country_from_url
        assert detect_country_from_url("https://item.taobao.com/item.htm?id=123") == "CN"
        assert detect_country_from_url("https://www.iherb.com/pr/12345") == "US"
        assert detect_country_from_url("https://www.amazon.co.jp/dp/B08XYZ") == "JP"
        assert detect_country_from_url("https://shopee.vn/product/123") == "VN"
        assert detect_country_from_url("https://unknown.com") == "CN"  # 기본값


class TestProductScore:
    def test_a_grade(self):
        from product_score import calculate_product_score
        r = calculate_product_score(
            margin_rate=40, trend_score=90, price_krw=30000,
            category="wellness", reorder_potential=True
        )
        assert r.grade == "A"
        assert r.total >= 90

    def test_d_grade(self):
        from product_score import calculate_product_score
        r = calculate_product_score(
            margin_rate=5, risk_flags=["의료기기", "의약품"],
            sourcing_decision="제외", trend_score=10
        )
        assert r.grade == "D"
        assert r.total < 50

    def test_score_breakdown(self):
        from product_score import calculate_product_score
        r = calculate_product_score(margin_rate=30, trend_score=70)
        assert "margin" in r.breakdown
        assert "risk" in r.breakdown
        assert "trend" in r.breakdown
        assert sum(r.breakdown.values()) == r.total


class TestPricingAgent:
    def test_cn_pricing(self):
        from pricing_agent import PricingAgent
        agent = PricingAgent()
        r = agent.execute({
            "source_price_cny": 50, "category": "wellness",
            "weight_kg": 0.3, "source_country": "CN"
        })
        assert r.is_success()
        assert r.output["final_price"] > 0
        assert r.output["margin_rate"] > -50  # 합리적 범위
        assert "source_price_krw" in r.output["cost_breakdown"]

    def test_us_pricing(self):
        from pricing_agent import PricingAgent
        agent = PricingAgent()
        r = agent.execute({
            "source_price_cny": 30, "category": "supplement",
            "weight_kg": 0.5, "source_country": "US"
        })
        assert r.is_success()
        # US는 환율이 높으므로 $30 = ~₩41,400
        assert r.output["final_price"] > 40000

    def test_pricing_decision(self):
        from pricing_agent import PricingAgent
        agent = PricingAgent()
        r = agent.execute({
            "source_price_cny": 10, "category": "general",
            "weight_kg": 0.1, "source_country": "CN"
        })
        assert r.is_success()
        assert r.output["pricing_decision"] in ("등록가능", "재검토", "제외")

    def test_multi_country_different_prices(self):
        from pricing_agent import PricingAgent
        agent = PricingAgent()
        prices = {}
        for cc in ["CN", "US", "JP", "VN"]:
            r = agent.execute({
                "source_price_cny": 50, "category": "wellness",
                "weight_kg": 0.3, "source_country": cc
            })
            prices[cc] = r.output["final_price"]
        # US는 환율이 높으므로 가장 비쌈
        assert prices["US"] > prices["CN"]


class TestComplianceFilter:
    def test_blocked_terms(self):
        from premium_detail_page import ComplianceFilter
        text, warnings = ComplianceFilter.clean("이 제품은 의료기기로 질병 치료에 효과적입니다")
        assert "의료기기" not in text
        assert len(warnings) > 0

    def test_replacements(self):
        from premium_detail_page import ComplianceFilter
        text, _ = ComplianceFilter.clean("치료 효과가 100% 보장됩니다")
        assert "치료" not in text
        assert "케어" in text
        assert "100%" not in text

    def test_clean_text_passes(self):
        from premium_detail_page import ComplianceFilter
        text, warnings = ComplianceFilter.clean("프리미엄 품질의 웰니스 제품입니다")
        assert text == "프리미엄 품질의 웰니스 제품입니다"
        assert len(warnings) == 0


class TestCacheManager:
    def _make_cache(self, name):
        from cache_manager import LLMCache
        tmp = os.path.join(tempfile.gettempdir(), f"test_{name}.db")
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass
        return LLMCache(tmp), tmp

    def test_set_and_get(self):
        cache, _ = self._make_cache("cache_a")
        cache.set("test", "collagen", {"result": "test_data"}, tokens_used=1000, category="wellness")
        result = cache.get("test", "collagen", category="wellness")
        assert result is not None
        assert result["result"] == "test_data"

    def test_cache_miss(self):
        cache, _ = self._make_cache("cache_b")
        result = cache.get("test", "nonexistent_product")
        assert result is None

    def test_stats(self):
        cache, _ = self._make_cache("cache_c")
        cache.set("premium", "test1", {"data": 1}, tokens_used=5000)
        cache.set("keyword", "test2", {"data": 2}, tokens_used=3000)
        cache.get("premium", "test1")  # hit

        stats = cache.stats()
        assert stats["total_entries"] == 2
        assert stats["total_hits"] == 1


class TestSalesTracker:
    def test_add_and_query(self):
        from sales_tracker import SalesTracker
        tmp = os.path.join(tempfile.gettempdir(), "test_sales_e2e.db")
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass
        tracker = SalesTracker(tmp)

        pid = tracker.add_product("test_collagen", "smartstore", "wellness", 29900, 10000)
        tracker.record_sales(pid, "2026-04-03", orders=10, revenue=299000, ad_spend=50000)

        perf = tracker.get_performance(pid, days=7)
        assert perf["total_orders"] == 10
        assert perf["total_revenue"] == 299000
        assert perf["roas"] > 0

        grade = tracker.grade_product(pid)
        assert grade in ("A", "B", "C", "D")


class TestAuth:
    def test_password_hashing(self):
        from auth import hash_password, verify_password
        h = hash_password("secure_password_123")
        assert verify_password("secure_password_123", h)
        assert not verify_password("wrong_password", h)

    def test_role_enum(self):
        from auth import Role
        assert Role.ADMIN == "admin"
        assert Role.OPERATOR == "operator"
        assert Role.VIEWER == "viewer"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
