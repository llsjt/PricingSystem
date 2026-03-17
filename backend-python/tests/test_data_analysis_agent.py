"""
DataAnalysisAgent 单元测试
测试重构后的数据分析 Agent 功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.data_analysis_agent import DataAnalysisAgent
from app.schemas.decision import (
    AnalysisRequest,
    ProductBase,
    SalesData,
    CompetitorData,
    RiskData,
    ReviewData
)
from colorama import init, Fore, Style

# 初始化 colorama
init()

def print_section(title):
    """打印章节标题"""
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{title}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")

def print_success(message):
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")

def print_error(message):
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")

def print_info(message):
    print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")

def create_test_request_1():
    """测试用例 1：正常商品（销量上升，库存正常）"""
    return AnalysisRequest(
        task_id="TEST001",
        product=ProductBase(
            product_id="P001",
            product_name="测试商品 A",
            category="数码",
            sub_category="蓝牙耳机",
            current_price=99.0,
            cost=50.0,
            original_price=129.0,
            stock=500,
            stock_age_days=30,
            is_new_product=False,
            is_seasonal=False,
            product_lifecycle_stage=None
        ),
        sales_data=SalesData(
            sales_history_7d=[10, 12, 11, 13, 15, 16, 18],  # 上升趋势
            sales_history_30d=list(range(10, 40)),  # 持续上升
            sales_history_90d=list(range(5, 95)),  # 长期上升
            pv_7d=[100, 120, 110, 130, 150, 160, 180],
            uv_7d=[50, 60, 55, 65, 75, 80, 90],
            conversion_rate_7d=0.15,
            promotion_history=[
                {"date": "2024-02-15", "discount_price": 89.0, "sales_before": 10, "sales_during": 18},
                {"date": "2024-03-01", "discount_price": 85.0, "sales_before": 12, "sales_during": 22},
                {"date": "2024-03-15", "discount_price": 90.0, "sales_before": 11, "sales_during": 20},
            ]
        ),
        competitor_data=CompetitorData(),
        risk_data=RiskData(),
        customer_reviews=[],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_2():
    """测试用例 2：积压商品（销量下降，库存积压）"""
    return AnalysisRequest(
        task_id="TEST002",
        product=ProductBase(
            product_id="P002",
            product_name="测试商品 B",
            category="服装",
            sub_category="T 恤",
            current_price=79.0,
            cost=35.0,
            original_price=99.0,
            stock=2000,  # 高库存
            stock_age_days=120,  # 库龄长
            is_new_product=False,
            is_seasonal=True,
            product_lifecycle_stage=None
        ),
        sales_data=SalesData(
            sales_history_7d=[50, 45, 40, 35, 30, 25, 20],  # 快速下降
            sales_history_30d=list(range(50, 20, -1)),  # 持续下降
            sales_history_90d=list(range(80, 20, -1)),  # 长期下降
            pv_7d=[200, 180, 160, 140, 120, 100, 80],
            uv_7d=[100, 90, 80, 70, 60, 50, 40],
            conversion_rate_7d=0.10,
            promotion_history=[]
        ),
        competitor_data=CompetitorData(),
        risk_data=RiskData(),
        customer_reviews=[],
        strategy_goal="CLEARANCE"
    )

def create_test_request_3():
    """测试用例 3：异常数据（检测刷单）"""
    return AnalysisRequest(
        task_id="TEST003",
        product=ProductBase(
            product_id="P003",
            product_name="测试商品 C",
            category="食品",
            sub_category="零食",
            current_price=39.9,
            cost=20.0,
            stock=100,
            stock_age_days=15,
            is_new_product=True,
            is_seasonal=False
        ),
        sales_data=SalesData(
            sales_history_7d=[5, 6, 5, 7, 6, 150, 5],  # 第 6 天异常峰值
            sales_history_30d=[5] * 30,  # 平稳
            sales_history_90d=[],
            pv_7d=[50] * 7,
            uv_7d=[25] * 7,
            conversion_rate_7d=0.12,
            promotion_history=[]
        ),
        competitor_data=CompetitorData(),
        risk_data=RiskData(),
        customer_reviews=[],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_4():
    """测试用例 4：库存紧缺"""
    return AnalysisRequest(
        task_id="TEST004",
        product=ProductBase(
            product_id="P004",
            product_name="测试商品 D",
            category="美妆",
            sub_category="面膜",
            current_price=69.0,
            cost=30.0,
            stock=20,  # 低库存
            stock_age_days=5,
            is_new_product=False,
            is_seasonal=False
        ),
        sales_data=SalesData(
            sales_history_7d=[30, 32, 35, 38, 40, 42, 45],  # 销量好
            sales_history_30d=list(range(20, 50)),
            sales_history_90d=list(range(10, 100)),
            pv_7d=[300, 320, 350, 380, 400, 420, 450],
            uv_7d=[150, 160, 175, 190, 200, 210, 225],
            conversion_rate_7d=0.20,
            promotion_history=[]
        ),
        competitor_data=CompetitorData(),
        risk_data=RiskData(),
        customer_reviews=[],
        strategy_goal="MAX_PROFIT"
    )

def test_data_analysis_agent(test_request: AnalysisRequest, test_name: str):
    """测试单个用例"""
    print_section(f"测试：{test_name}")
    
    try:
        agent = DataAnalysisAgent()
        
        print_info(f"任务 ID: {test_request.task_id}")
        print_info(f"商品：{test_request.product.product_name}")
        print_info(f"价格：¥{test_request.product.current_price} (成本：¥{test_request.product.cost})")
        print_info(f"库存：{test_request.product.stock} 件 (库龄：{test_request.product.stock_age_days}天)")
        print_info(f"战略目标：{test_request.strategy_goal}")
        
        # 执行分析
        print(f"\n{Fore.YELLOW}正在执行数据分析...{Style.RESET_ALL}\n")
        result = agent.analyze(test_request)
        
        # 输出结果
        print(f"{Fore.GREEN}=== 分析结果 ==={Style.RESET_ALL}")
        print(f"✓ 销量趋势：{result.sales_trend} (得分：{result.sales_trend_score:.2f})")
        print(f"✓ 库存状态：{result.inventory_status} (健康度：{result.inventory_health_score:.1f})")
        print(f"✓ 预估周转天数：{result.estimated_turnover_days or 'N/A'}")
        
        if result.demand_elasticity:
            print(f"✓ 价格弹性系数：{result.demand_elasticity:.2f} (置信度：{result.demand_elasticity_confidence:.1%})")
        
        print(f"✓ 生命周期阶段：{result.product_lifecycle_stage}")
        print(f"  判断依据：{result.lifecycle_evidence}")
        
        if result.has_anomalies:
            print(f"\n{Fore.YELLOW}⚠ 检测到{len(result.anomaly_list)}个异常：{Style.RESET_ALL}")
            for anomaly in result.anomaly_list:
                print(f"  - [{anomaly['severity'].upper()}] {anomaly['description']}")
        else:
            print(f"\n✓ 未检测到数据异常")
        
        print(f"\n{Fore.CYAN}=== 建议 ==={Style.RESET_ALL}")
        print(f"建议操作：{result.recommended_action}")
        print(f"建议折扣区间：{result.recommended_discount_range[0]:.0%} - {result.recommended_discount_range[1]:.0%}")
        print(f"建议置信度：{result.recommendation_confidence:.1%}")
        
        print(f"\n理由：")
        for i, reason in enumerate(result.recommendation_reasons, 1):
            print(f"  {i}. {reason}")
        
        print(f"\n{Fore.BLUE}=== 数据质量 ==={Style.RESET_ALL}")
        print(f"数据质量评分：{result.data_quality_score:.1%}")
        
        if result.limitations:
            print(f"\n局限性说明：")
            for i, limit in enumerate(result.limitations, 1):
                print(f"  {i}. {limit}")
        
        print(f"\n{Fore.GREEN}=== 详细计算过程 ==={Style.RESET_ALL}")
        if result.analysis_details:
            if 'sales_trend_calculation' in result.analysis_details:
                trend_calc = result.analysis_details['sales_trend_calculation']
                print(f"销量趋势计算：")
                print(f"  短期趋势：{trend_calc.get('short_term_trend', 'N/A'):.2f}")
                print(f"  中期趋势：{trend_calc.get('mid_term_trend', 'N/A'):.2f}")
                print(f"  长期趋势：{trend_calc.get('long_term_trend', 'N/A'):.2f}")
                print(f"  综合得分：{trend_calc.get('composite_score', 'N/A'):.2f}")
                print(f"  计算公式：{trend_calc.get('formula', 'N/A')}")
            
            if 'inventory_health_calculation' in result.analysis_details:
                inv_calc = result.analysis_details['inventory_health_calculation']
                print(f"\n库存健康度计算：")
                print(f"  周转天数：{inv_calc.get('turnover_days', 'N/A'):.1f}")
                print(f"  目标周转：{inv_calc.get('target_turnover_days', 'N/A')}天")
                print(f"  库龄：{inv_calc.get('stock_age_days', 'N/A')}天")
                print(f"  计算公式：{inv_calc.get('formula', 'N/A')}")
        
        print_success(f"测试通过！\n")
        return True
        
    except Exception as e:
        print_error(f"测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}DataAnalysisAgent 功能测试{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    test_cases = [
        (create_test_request_1(), "正常商品（销量上升，库存正常）"),
        (create_test_request_2(), "积压商品（销量下降，库存积压）"),
        (create_test_request_3(), "异常数据（检测刷单）"),
        (create_test_request_4(), "库存紧缺商品"),
    ]
    
    results = {}
    
    for request, name in test_cases:
        results[name] = test_data_analysis_agent(request, name)
    
    # 汇总结果
    print_section("测试结果汇总")
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for name, result in results.items():
        if result:
            print_success(f"✓ {name}: 通过")
        else:
            print_error(f"✗ {name}: 失败")
    
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"总计：{total} 个测试")
    print(f"{Fore.GREEN}通过：{passed}{Style.RESET_ALL}")
    if failed > 0:
        print(f"{Fore.RED}失败：{failed}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    if passed == total:
        print_success("🎉 所有测试通过！DataAnalysisAgent 功能正常！")
        return 0
    else:
        print_error("❌ 部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print_error(f"测试过程中发生未预期的错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
