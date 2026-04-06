"""
Sales Tracker API — 매출 데이터 (수동 입력 + 통계)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException
from sales_tracker import SalesTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sales", tags=["sales"])


@router.post("/add")
async def add_sale(
    platform: str = Form(...),
    product_name: str = Form(...),
    selling_price: float = Form(...),
    quantity: int = Form(1),
    cost_price: float = Form(0),
    order_date: Optional[str] = Form(None),
    option_name: str = Form(""),
):
    """수동 매출 입력"""
    tracker = SalesTracker()
    sale_id = tracker.add_sale(
        platform=platform,
        product_name=product_name,
        selling_price=selling_price,
        quantity=quantity,
        cost_price=cost_price,
        order_date=order_date,
        option_name=option_name,
    )
    return {"sale_id": sale_id}


@router.get("/stats")
async def sales_stats(days: int = 30):
    """매출 통계 (COO 대시보드용)"""
    tracker = SalesTracker()
    return tracker.get_dashboard_stats(days)


@router.get("/product/{product_name}")
async def product_performance(product_name: str):
    """개별 상품 실적"""
    tracker = SalesTracker()
    return tracker.get_product_performance(product_name)
