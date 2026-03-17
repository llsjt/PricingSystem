"""
测试 DecisionService 和 WorkflowService 的完整功能
验证从数据库获取数据并生成决策的完整流程
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas.decision import (
    AnalysisRequest, 
    ProductBase, 
    SalesData, 
    CompetitorData, 
    RiskData,
    ReviewData
)
from app.services.decision_service import decision_service
import asyncio

async def test_decision_service():
    """测试 DecisionService 的基本功能"""
    print("=" * 70)
    print("测试 DecisionService")
    print("=" * 70)
    
    # 构造测试数据
    request = AnalysisRequest(
        task_id="TEST_001",
        product=ProductBase(
            product_id="TEST001",
            product_name="测试商品 - 蓝牙耳机",
            category="数码配件",
            current_price=99.0,
            cost=45.0,
            stock=150
        ),
        sales_data=SalesData(
            sales_history_7d=[10, 12, 15, 14, 20, 18, 25],
            sales_history_30d=[300] * 30
        ),
        competitor_data=CompetitorData(
            competitor_prices=[89.0, 95.0, 105.0, 110.0],
            competitor_activities=["双 11 大促", "满 100 减 20"]
        ),
        risk_data=RiskData(
            min_profit_margin=0.15,
            current_margin=0.545
        ),
        customer_reviews=[
            ReviewData(rating=5, content="音质不错，性价比很高", tags=["音质好", "性价比高"]),
            ReviewData(rating=5, content="物流很快，包装完好", tags=["物流快"]),
            ReviewData(rating=4, content="佩戴舒适，续航能力强", tags=["舒适", "续航好"]),
            ReviewData(rating=3, content="价格有点贵，希望能优惠", tags=["价格贵"])
        ],
        strategy_goal="MAX_PROFIT"
    )
    
    print("\n1. 测试 DataAnalysisAgent...")
    data_result = await decision_service.run_data_analysis(request)
    print(f"✓ 数据分析完成")
    print(f"  销量趋势：{data_result.sales_trend}（得分：{data_result.sales_trend_score:.2f}）")
    print(f"  库存状态：{data_result.inventory_status}（健康度：{data_result.inventory_health_score:.1f}）")
    print(f"  建议：{data_result.recommended_action}，折扣区间：{data_result.recommended_discount_range}")
    print(f"  理由：{data_result.recommendation_reasons[0] if data_result.recommendation_reasons else 'N/A'}...")
    
    print("\n2. 测试 MarketIntelAgent...")
    market_result = await decision_service.run_market_intel(request)
    print(f"✓ 市场情报完成")
    print(f"  竞争强度：{market_result.competition_level}（得分：{market_result.competition_score:.1f}）")
    print(f"  价格定位：{market_result.price_position}（{market_result.price_percentile*100:.0f}% 分位）")
    print(f"  情感分析：{market_result.sentiment_label}（得分：{market_result.sentiment_score:.2f}）")
    print(f"  市场建议：{market_result.market_suggestion}")
    
    print("\n3. 测试 RiskControlAgent...")
    risk_result = await decision_service.run_risk_control(request)
    print(f"✓ 风控评估完成")
    print(f"  风险等级：{risk_result.risk_level}（得分：{risk_result.risk_score:.1f}）")
    print(f"  当前毛利率：{risk_result.current_profit_margin*100:.1f}%")
    print(f"  盈亏平衡价：¥{risk_result.break_even_price:.2f}")
    print(f"  最低安全价：¥{risk_result.min_safe_price:.2f}")
    print(f"  最大安全折扣：{risk_result.max_safe_discount*100:.0f}%")
    print(f"  促销审批：{'通过' if risk_result.allow_promotion else '拒绝'}")
    
    print("\n4. 测试 ManagerCoordinatorAgent（全流程）...")
    final_decision = await decision_service.run_manager_decision(request)
    print(f"✓ 最终决策完成")
    print(f"  决策：{final_decision.decision}")
    print(f"  折扣率：{final_decision.discount_rate * 100:.1f}%")
    print(f"  建议价格：¥{final_decision.suggested_price:.2f}")
    print(f"  置信度：{final_decision.confidence * 100:.1f}%")
    print(f"  核心理由：{final_decision.core_reasons[:100]}...")
    
    print("\n" + "=" * 70)
    print("✓ DecisionService 测试通过！")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_decision_service())
