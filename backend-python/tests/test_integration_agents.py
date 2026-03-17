"""
ManagerCoordinatorAgent 集成测试
测试 4 个 Agent 的完整协作流程
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.manager_coordinator_agent import ManagerCoordinatorAgent
from app.schemas.decision import (
    AnalysisRequest,
    ProductBase,
    SalesData,
    CompetitorData,
    CompetitorInfo,
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

def print_warning(message):
    print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")

def create_test_request_1():
    """测试用例 1：利润最大化战略（健康商品）"""
    return AnalysisRequest(
        task_id="INTEGRATION_001",
        product=ProductBase(
            product_id="P001",
            product_name="蓝牙耳机 X1",
            category="数码",
            sub_category="蓝牙耳机",
            current_price=99.0,
            cost=50.0,
            original_price=129.0,
            stock=500,
            stock_age_days=30,
            is_new_product=False
        ),
        sales_data=SalesData(
            sales_history_7d=[10, 12, 11, 13, 15, 16, 18],
            sales_history_30d=list(range(10, 40)),
            sales_history_90d=list(range(5, 95)),
            promotion_history=[
                {"date": "2024-02-15", "discount_price": 89.0, "sales_before": 10, "sales_during": 18},
                {"date": "2024-03-01", "discount_price": 85.0, "sales_before": 12, "sales_during": 22},
            ]
        ),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=89.0, rating=4.5, promotion_tags=["降价"]),
                CompetitorInfo(competitor_id="C002", product_name="竞品 B", current_price=95.0, rating=4.3),
            ],
            category_total_sales=50000
        ),
        risk_data=RiskData(
            min_profit_margin=0.15,
            refund_rate=0.03,
            complaint_rate=0.005,
            cash_conversion_cycle=25
        ),
        customer_reviews=[
            ReviewData(rating=5, content="音质很好，性价比高", tags=["音质好", "性价比高"]),
            ReviewData(rating=4, content="不错，推荐购买", tags=["推荐"]),
        ],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_2():
    """测试用例 2：市场份额战略（竞争激烈）"""
    return AnalysisRequest(
        task_id="INTEGRATION_002",
        product=ProductBase(
            product_id="P002",
            product_name="时尚 T 恤",
            category="服装",
            current_price=79.0,
            cost=35.0,
            stock=1000,
            stock_age_days=45
        ),
        sales_data=SalesData(
            sales_history_7d=[50, 48, 45, 42, 40, 38, 35],  # 下降趋势
            sales_history_30d=list(range(50, 20, -1))
        ),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=69.0, rating=4.4, promotion_tags=["打折", "满减"]),
                CompetitorInfo(competitor_id="C002", product_name="竞品 B", current_price=65.0, rating=4.2, promotion_tags=["促销"]),
                CompetitorInfo(competitor_id="C003", product_name="竞品 C", current_price=72.0, rating=4.5, promotion_tags=["秒杀"]),
            ],
            category_total_sales=100000
        ),
        risk_data=RiskData(
            min_profit_margin=0.20,
            refund_rate=0.05,
            cash_conversion_cycle=35
        ),
        customer_reviews=[
            ReviewData(rating=4, content="质量不错，款式好看", tags=["质量好"]),
            ReviewData(rating=3, content="价格有点贵", tags=["贵"]),
        ],
        strategy_goal="MARKET_SHARE"
    )

def create_test_request_3():
    """测试用例 3：清仓战略（高风险商品）"""
    return AnalysisRequest(
        task_id="INTEGRATION_003",
        product=ProductBase(
            product_id="P003",
            product_name="过季羽绒服",
            category="服装",
            current_price=299.0,
            cost=200.0,
            stock=500,
            stock_age_days=180  # 库龄很长
        ),
        sales_data=SalesData(
            sales_history_7d=[5, 4, 3, 2, 1, 0, 0],  # 几乎滞销
            sales_history_30d=[5] * 30
        ),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=199.0, rating=4.3),
            ]
        ),
        risk_data=RiskData(
            min_profit_margin=0.10,  # 清仓时降低要求
            refund_rate=0.08,
            cash_conversion_cycle=60
        ),
        customer_reviews=[
            ReviewData(rating=3, content="质量可以，但是过季了", tags=["过季"]),
        ],
        strategy_goal="CLEARANCE"
    )

def test_manager_coordinator(test_request: AnalysisRequest, test_name: str):
    """测试单个用例"""
    print_section(f"集成测试：{test_name}")
    
    try:
        agent = ManagerCoordinatorAgent()
        
        print_info(f"任务 ID: {test_request.task_id}")
        print_info(f"商品：{test_request.product.product_name}")
        print_info(f"价格：¥{test_request.product.current_price}")
        print_info(f"战略目标：{test_request.strategy_goal}")
        
        # 执行全流程决策
        print(f"\n{Fore.YELLOW}正在执行 Multi-Agent 决策流程...{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}预计耗时：1-2 秒{Style.RESET_ALL}\n")
        
        result = agent.make_decision(test_request)
        
        # 输出结果
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
        print(f"{Fore.GREEN}=== 最终决策 ==={Style.RESET_ALL}")
        print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")
        
        print(f"✓ 决策结论：{result.decision}")
        print(f"✓ 折扣率：{result.discount_rate:.0%}")
        print(f"✓ 建议价格：¥{result.suggested_price:.2f}")
        print(f"✓ 置信度：{result.confidence:.1%}")
        
        if result.expected_outcomes:
            print(f"\n{Fore.CYAN}=== 预期结果 ==={Style.RESET_ALL}")
            print(f"✓ 销量提升：{result.expected_outcomes.sales_lift:.1%}")
            print(f"✓ 利润变化：{result.expected_outcomes.profit_change:+.1%}")
            print(f"✓ 市场份额：{result.expected_outcomes.market_share_change:+.1%}")
        
        print(f"\n{Fore.YELLOW}=== Agent 分析摘要 ==={Style.RESET_ALL}")
        for summary in result.agent_summaries:
            print(f"\n**{summary.agent_name}**:")
            print(f"  {summary.summary}")
            if summary.key_points:
                for point in summary.key_points[:2]:
                    print(f"  - {point}")
        
        if result.conflicts_detected:
            print(f"\n{Fore.RED}=== 冲突检测与解决 ==={Style.RESET_ALL}")
            for conflict in result.conflicts_detected:
                print(f"⚠ {conflict.agent1} vs {conflict.agent2}")
                print(f"  冲突：{conflict.conflict}")
                print(f"  解决：{conflict.resolution}")
                print(f"  优先级：{conflict.priority}")
        
        print(f"\n{Fore.GREEN}=== 核心理由 ==={Style.RESET_ALL}")
        print(f"{result.core_reasons}")
        
        print(f"\n{Fore.MAGENTA}=== 风险提示 ==={Style.RESET_ALL}")
        print(f"{result.risk_warning}")
        
        print(f"\n{Fore.BLUE}=== 应急预案 ==={Style.RESET_ALL}")
        print(f"{result.contingency_plan}")
        
        print(f"\n{Fore.CYAN}=== 执行计划 ==={Style.RESET_ALL}")
        for plan in result.execution_plan[:3]:  # 只显示前 3 步
            print(f"{plan.step}. {plan.action}")
            print(f"   时间：{plan.timing} | 负责人：{plan.responsible}")
        
        if result.key_factors:
            print(f"\n{Fore.BLUE}=== 关键因素 ==={Style.RESET_ALL}")
            for factor in result.key_factors:
                print(f"  - {factor}")
        
        # 显示决策框架（简化版）
        print(f"\n{Fore.WHITE}=== 决策框架 ==={Style.RESET_ALL}")
        lines = result.decision_framework.split('\n')
        for line in lines[:10]:  # 只显示前 10 行
            print(line)
        if len(lines) > 10:
            print("...（报告过长，已省略）")
        
        # 显示报告文本（前 20 行）
        print(f"\n{Fore.WHITE}=== 完整报告（前 20 行）=== {Style.RESET_ALL}")
        report_lines = result.report_text.split('\n')
        for line in report_lines[:20]:
            print(line)
        if len(report_lines) > 20:
            print("...（报告过长，已省略）")
        
        print_success(f"集成测试通过！\n")
        return True
        
    except Exception as e:
        print_error(f"测试失败：{e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}Multi-Agent 集成测试{Style.RESET_ALL}")
    print(f"{Fore.GREEN}测试 4 个 Agent 的完整协作流程{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    test_cases = [
        (create_test_request_1(), "利润最大化战略（健康商品）"),
        (create_test_request_2(), "市场份额战略（竞争激烈）"),
        (create_test_request_3(), "清仓战略（高风险商品）"),
    ]
    
    results = {}
    
    for request, name in test_cases:
        results[name] = test_manager_coordinator(request, name)
    
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
        print_success("🎉 所有集成测试通过！Multi-Agent 系统功能正常！")
        print(f"\n{Fore.GREEN}4 个 Agent 重构完成并通过测试：{Style.RESET_ALL}")
        print("  1. ✓ DataAnalysisAgent")
        print("  2. ✓ MarketIntelAgent")
        print("  3. ✓ RiskControlAgent")
        print("  4. ✓ ManagerCoordinatorAgent")
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
