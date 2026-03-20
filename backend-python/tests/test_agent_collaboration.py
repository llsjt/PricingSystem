from __future__ import annotations

import asyncio

from pricing_crew.decision_service import decision_service
from pricing_crew.schemas import (
    AnalysisRequest,
    CompetitorData,
    CompetitorInfo,
    ProductBase,
    ReviewData,
    RiskData,
    SalesData,
)


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


def test_four_agent_collaboration():
    request = build_request()
    data_result, market_result, risk_result, final_result = asyncio.run(decision_service.run_full_decision(request))

    assert data_result.sales_trend
    assert market_result.market_suggestion in {"maintain", "discount", "penetrate", "price_war", "premium", "differentiate"}
    assert risk_result.recommendation in {"maintain", "discount", "increase"}
    assert final_result.decision in {"maintain", "discount", "increase"}
    assert final_result.suggested_price > 0


def test_manager_stage_with_inputs():
    request = build_request()
    data_result, market_result, risk_result, _ = asyncio.run(decision_service.run_full_decision(request))

    manager_result = asyncio.run(
        decision_service.run_manager_decision(
            request=request,
            data_result=data_result,
            market_result=market_result,
            risk_result=risk_result,
        )
    )

    assert manager_result.decision in {"maintain", "discount", "increase"}
    assert manager_result.confidence >= 0.3


def test_price_floor_constraint_forces_increase():
    request = AnalysisRequest(
        task_id="PRICE_FLOOR_CASE",
        product=ProductBase(
            product_id="P_FLOOR_001",
            product_name="Constraint Product",
            category="户外服饰",
            current_price=139.0,
            cost=48.0,
            stock=320,
            stock_age_days=50,
        ),
        sales_data=SalesData(
            sales_history_7d=[13, 14, 12, 13, 14, 13, 15],
            sales_history_30d=[13] * 30,
            sales_history_90d=[12] * 90,
        ),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(
                    competitor_id="C_FLOOR_001",
                    product_name="Competitor Floor A",
                    current_price=129.0,
                    rating=4.6,
                    review_count=1800,
                    promotion_tags=["包邮"],
                )
            ]
        ),
        risk_data=RiskData(
            min_profit_margin=0.18,
            price_floor=189.0,
            enforce_hard_constraints=True,
        ),
        strategy_goal="MAX_PROFIT",
    )

    _, _, risk_result, final_result = asyncio.run(decision_service.run_full_decision(request))

    assert risk_result.required_min_price >= 189.0
    assert final_result.decision == "increase"
    assert final_result.suggested_price == 189.0
