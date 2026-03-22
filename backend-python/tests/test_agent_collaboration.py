from __future__ import annotations

import asyncio

from pricing_crew.agent_logic import run_manager_coordinator_agent
from pricing_crew.decision_service import decision_service
from pricing_crew.schemas import (
    AnalysisRequest,
    CompetitorData,
    CompetitorInfo,
    DataAnalysisResult,
    MarketIntelResult,
    ProductBase,
    ReviewData,
    RiskData,
    RiskControlResult,
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


def _build_manager_inputs(elasticity: float):
    request = AnalysisRequest(
        task_id="MANAGER_PROFIT_CASE",
        product=ProductBase(
            product_id="P_MANAGER_001",
            product_name="Profit Case Product",
            category="Electronics",
            current_price=100.0,
            cost=40.0,
            stock=500,
            stock_age_days=90,
        ),
        sales_data=SalesData(
            sales_history_7d=[100] * 7,
            sales_history_30d=[100] * 30,
            sales_history_90d=[95] * 90,
        ),
        competitor_data=CompetitorData(competitors=[]),
        risk_data=RiskData(min_profit_margin=0.15, enforce_hard_constraints=True),
        strategy_goal="MAX_PROFIT",
    )

    data_result = DataAnalysisResult(
        sales_trend="declining",
        sales_trend_score=-0.3,
        inventory_status="overstock",
        inventory_health_score=42.0,
        demand_elasticity=elasticity,
        recommended_action="discount",
        recommended_discount_range=(0.95, 0.97),
        recommendation_confidence=0.8,
        recommendation_reasons=["库存偏高，需要测试降价"],
        analysis_details={"avg_sales_30d": 100.0},
        decision_summary="数据分析建议：discount",
        confidence=0.8,
    )

    market_result = MarketIntelResult(
        competition_level="moderate",
        competition_score=0.45,
        price_position="mid-range",
        price_percentile=0.5,
        market_suggestion="maintain",
        suggestion_confidence=0.7,
        suggestion_reasons=["市场价格带稳定"],
        analysis_details={"live_market_available": True},
        decision_summary="市场情报建议：maintain",
        confidence=0.7,
    )

    risk_result = RiskControlResult(
        current_profit_margin=0.6,
        break_even_price=40.0,
        min_safe_price=47.06,
        required_min_price=47.06,
        risk_level="low",
        risk_score=20.0,
        allow_promotion=True,
        max_safe_discount=0.9,
        recommendation="discount",
        recommendation_reasons=["风险可控"],
        calculation_details={
            "constraint_conflict": False,
            "floor_breach": False,
            "ceiling_breach": False,
            "total_cost": 40.0,
        },
        confidence=0.8,
    )

    return request, data_result, market_result, risk_result


def test_manager_profit_change_uses_expected_profit_delta():
    request, data_result, market_result, risk_result = _build_manager_inputs(elasticity=-2.5)

    final_result = run_manager_coordinator_agent(request, data_result, market_result, risk_result)

    assert final_result.decision == "discount"
    assert final_result.expected_outcomes is not None
    assert final_result.expected_outcomes.sales_lift > 1.0
    assert final_result.expected_outcomes.profit_change > 0


def test_manager_can_choose_profitable_increase_for_max_profit():
    request = AnalysisRequest(
        task_id="MANAGER_INCREASE_CASE",
        product=ProductBase(
            product_id="P_MANAGER_002",
            product_name="Increase Case Product",
            category="Electronics",
            current_price=100.0,
            cost=40.0,
            stock=180,
            stock_age_days=45,
        ),
        sales_data=SalesData(
            sales_history_7d=[100] * 7,
            sales_history_30d=[100] * 30,
            sales_history_90d=[98] * 90,
        ),
        competitor_data=CompetitorData(competitors=[]),
        risk_data=RiskData(min_profit_margin=0.15, enforce_hard_constraints=True),
        strategy_goal="MAX_PROFIT",
    )

    data_result = DataAnalysisResult(
        sales_trend="stable",
        sales_trend_score=0.0,
        inventory_status="normal",
        inventory_health_score=76.0,
        demand_elasticity=-0.9,
        recommended_action="maintain",
        recommended_discount_range=(1.0, 1.0),
        recommendation_confidence=0.8,
        recommendation_reasons=["经营信号稳定"],
        analysis_details={"avg_sales_30d": 100.0},
        decision_summary="数据分析建议：maintain",
        confidence=0.8,
    )

    market_result = MarketIntelResult(
        competition_level="moderate",
        competition_score=0.45,
        price_position="mid-range",
        price_percentile=0.5,
        market_suggestion="maintain",
        suggestion_confidence=0.75,
        suggestion_reasons=["价格带稳定"],
        analysis_details={"live_market_available": True},
        decision_summary="市场情报建议：maintain",
        confidence=0.75,
    )

    risk_result = RiskControlResult(
        current_profit_margin=0.6,
        break_even_price=40.0,
        min_safe_price=47.06,
        required_min_price=47.06,
        risk_level="low",
        risk_score=18.0,
        allow_promotion=True,
        max_safe_discount=0.9,
        recommendation="maintain",
        recommendation_reasons=["风险可控"],
        calculation_details={
            "constraint_conflict": False,
            "floor_breach": False,
            "ceiling_breach": False,
            "total_cost": 40.0,
        },
        confidence=0.82,
    )

    final_result = run_manager_coordinator_agent(request, data_result, market_result, risk_result)

    assert final_result.decision == "increase"
    assert final_result.suggested_price > 100.0
    assert final_result.expected_outcomes is not None
    assert final_result.expected_outcomes.profit_change > 0


def test_manager_avoids_unprofitable_discount_for_max_profit():
    request, data_result, market_result, risk_result = _build_manager_inputs(elasticity=-0.3)
    market_result.market_suggestion = "discount"
    market_result.competition_level = "fierce"
    market_result.price_position = "premium"

    final_result = run_manager_coordinator_agent(request, data_result, market_result, risk_result)

    assert final_result.decision in {"maintain", "increase"}
    assert final_result.suggested_price >= 100.0
    assert final_result.expected_outcomes is not None
    assert final_result.expected_outcomes.profit_change >= 0.0
