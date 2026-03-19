"""
4-agent flow smoke test.

This script validates:
1. DataAnalysis stage
2. MarketIntel stage
3. RiskControl stage
4. Manager stage (with upstream outputs)
5. End-to-end full flow
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.decision import (  # noqa: E402
    AnalysisRequest,
    CompetitorData,
    CompetitorInfo,
    ProductBase,
    ReviewData,
    RiskData,
    SalesData,
)
from app.services.decision_service import decision_service  # noqa: E402


def build_request() -> AnalysisRequest:
    return AnalysisRequest(
        task_id="SMOKE_4_AGENT_FLOW",
        product=ProductBase(
            product_id="P_SMOKE_001",
            product_name="Smoke Product",
            category="Electronics",
            current_price=129.0,
            cost=79.0,
            stock=220,
            stock_age_days=20,
        ),
        sales_data=SalesData(
            sales_history_7d=[10, 11, 12, 11, 13, 12, 14],
            sales_history_30d=[12] * 30,
            sales_history_90d=[11] * 90,
        ),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(
                    competitor_id="C001",
                    product_name="Competitor A",
                    current_price=119.0,
                    rating=4.4,
                    review_count=900,
                    promotion_tags=["discount"],
                ),
                CompetitorInfo(
                    competitor_id="C002",
                    product_name="Competitor B",
                    current_price=135.0,
                    rating=4.5,
                    review_count=850,
                    promotion_tags=[],
                ),
            ]
        ),
        risk_data=RiskData(
            min_profit_margin=0.15,
            refund_rate=0.03,
            complaint_rate=0.01,
            enforce_hard_constraints=True,
        ),
        customer_reviews=[
            ReviewData(rating=5, content="Good quality", tags=["quality"]),
            ReviewData(rating=4, content="Worth buying", tags=["value"]),
        ],
        strategy_goal="MAX_PROFIT",
    )


async def main() -> int:
    request = build_request()

    print("== 4-agent stage checks ==")
    data_result = await decision_service.run_data_analysis(request)
    assert data_result.sales_trend
    assert len(data_result.recommended_discount_range) == 2
    print("data_analysis: ok")

    market_result = await decision_service.run_market_intel(request)
    assert market_result.market_suggestion
    print("market_intel: ok")

    risk_result = await decision_service.run_risk_control(request)
    assert risk_result.recommendation in {"maintain", "discount", "increase"}
    print("risk_control: ok")

    manager_result = await decision_service.run_manager_decision(
        request=request,
        data_result=data_result,
        market_result=market_result,
        risk_result=risk_result,
    )
    assert manager_result.decision in {"maintain", "discount", "increase"}
    print("manager_decision: ok")

    print("== full flow check ==")
    data2, market2, risk2, final2 = await decision_service.run_full_decision(request)
    assert data2.sales_trend
    assert market2.market_suggestion
    assert risk2.recommendation in {"maintain", "discount", "increase"}
    assert final2.decision in {"maintain", "discount", "increase"}
    print("full_flow: ok")

    print(
        f"decision={final2.decision}, suggested_price={final2.suggested_price}, "
        f"framework={final2.decision_framework}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
