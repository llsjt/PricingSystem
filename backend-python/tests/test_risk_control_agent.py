"""
RiskControlAgent 单元测试
测试重构后的风险控制 Agent 功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.risk_control_agent import RiskControlAgent
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

def print_warning(message):
    print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")

def create_test_request_1():
    """测试用例 1：健康商品（利润充足，风险低）"""
    return AnalysisRequest(
        task_id="TEST_RC_001",
        product=ProductBase(
            product_id="P001",
            product_name="蓝牙耳机 X1",
            category="数码",
            current_price=99.0,
            cost=50.0,
            original_price=129.0,
            stock=500,
            stock_age_days=30,
            is_new_product=False
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(),
        risk_data=RiskData(
            min_profit_margin=0.15,
            target_profit_margin=0.30,
            refund_rate=0.03,
            complaint_rate=0.005,
            cost_breakdown={
                "material_cost": 50.0,
                "labor_cost": 5.0,
                "shipping_cost": 3.0,
                "platform_commission": 4.95,  # 99 * 0.05
                "marketing_cost": 2.0
            },
            cash_conversion_cycle=25
        ),
        customer_reviews=[],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_2():
    """测试用例 2：高风险商品（利润微薄，库存积压）"""
    return AnalysisRequest(
        task_id="TEST_RC_002",
        product=ProductBase(
            product_id="P002",
            product_name="过季服装",
            category="服装",
            current_price=79.0,
            cost=65.0,  # 成本高
            stock=2000,  # 高库存
            stock_age_days=150,  # 库龄长
            is_new_product=False
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(),
        risk_data=RiskData(
            min_profit_margin=0.20,
            refund_rate=0.18,  # 高退款率
            complaint_rate=0.04,  # 高投诉率
            cash_conversion_cycle=75  # 现金流紧张
        ),
        customer_reviews=[],
        strategy_goal="CLEARANCE"
    )

def create_test_request_3():
    """测试用例 3：品牌控价商品（有限价约束）"""
    return AnalysisRequest(
        task_id="TEST_RC_003",
        product=ProductBase(
            product_id="P003",
            product_name="品牌化妆品",
            category="美妆",
            current_price=299.0,
            cost=150.0,
            stock=300,
            stock_age_days=20
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(),
        risk_data=RiskData(
            min_profit_margin=0.25,
            refund_rate=0.02,
            complaint_rate=0.005,
            is_brand_controlled=True,
            price_floor=269.0,  # 品牌方限价
            cash_conversion_cycle=30
        ),
        customer_reviews=[],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_4():
    """测试用例 4：接近盈亏平衡点（利润极薄）"""
    return AnalysisRequest(
        task_id="TEST_RC_004",
        product=ProductBase(
            product_id="P004",
            product_name="引流商品",
            category="食品",
            current_price=39.9,
            cost=35.0,  # 成本接近售价
            stock=100,
            stock_age_days=10
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(),
        risk_data=RiskData(
            min_profit_margin=0.15,
            refund_rate=0.05,
            complaint_rate=0.01,
            cash_conversion_cycle=15
        ),
        customer_reviews=[],
        strategy_goal="MARKET_SHARE"
    )

def test_risk_control_agent(test_request: AnalysisRequest, test_name: str):
    """测试单个用例"""
    print_section(f"测试：{test_name}")
    
    try:
        agent = RiskControlAgent()
        
        print_info(f"任务 ID: {test_request.task_id}")
        print_info(f"商品：{test_request.product.product_name}")
        print_info(f"价格：¥{test_request.product.current_price} (成本：¥{test_request.product.cost})")
        print_info(f"库存：{test_request.product.stock} 件 (库龄：{test_request.product.stock_age_days}天)")
        print_info(f"战略目标：{test_request.strategy_goal}")
        
        # 执行分析
        print(f"\n{Fore.YELLOW}正在执行风险控制分析...{Style.RESET_ALL}\n")
        result = agent.analyze(test_request)
        
        # 输出结果
        print(f"{Fore.GREEN}=== 财务指标 ==={Style.RESET_ALL}")
        print(f"✓ 当前毛利率：{result.current_profit_margin:.1%}")
        if result.profit_margin_after_discount:
            print(f"✓ 折后毛利率：{result.profit_margin_after_discount:.1%}")
        
        print(f"\n{Fore.CYAN}=== 价格红线 ==={Style.RESET_ALL}")
        print(f"✓ 盈亏平衡价：¥{result.break_even_price:.2f}")
        print(f"✓ 最低安全价：¥{result.min_safe_price:.2f}")
        if result.absolute_price_floor:
            print(f"✓ 绝对底线（品牌限价）：¥{result.absolute_price_floor:.2f}")
        
        print(f"\n{Fore.YELLOW}=== 风险评估 ==={Style.RESET_ALL}")
        print(f"✓ 风险等级：{result.risk_level} (得分：{result.risk_score:.1f})")
        print(f"✓ 风险明细：")
        for risk_type, score in result.risk_breakdown.items():
            print(f"    - {risk_type}: {score:.1f}")
        
        print(f"\n{Fore.RED}=== 促销审批（一票否决权）==={Style.RESET_ALL}")
        if result.allow_promotion:
            print_success(f"允许促销")
            print(f"✓ 最大安全折扣：{result.max_safe_discount:.0%}")
            if result.discount_conditions:
                print_warning(f"附加条件：")
                for condition in result.discount_conditions:
                    print(f"    - {condition}")
        else:
            print_error(f"禁止促销")
            if result.veto_reason:
                print_warning(f"否决理由：{result.veto_reason}")
        
        print(f"\n{Fore.MAGENTA}=== 风险预警 ==={Style.RESET_ALL}")
        if result.warnings:
            for warning in result.warnings:
                print_warning(f"⚠ {warning}")
        else:
            print_success("无风险预警")
        
        print(f"\n{Fore.GREEN}=== 建议 ==={Style.RESET_ALL}")
        print(f"建议策略：{result.recommendation}")
        print(f"理由：")
        for i, reason in enumerate(result.recommendation_reasons, 1):
            print(f"  {i}. {reason}")
        
        print(f"\n{Fore.BLUE}=== 合规检查 ==={Style.RESET_ALL}")
        if result.compliance_check:
            print_success("通过合规检查")
        else:
            print_error("未通过合规检查")
        
        print(f"\n{Fore.CYAN}=== 详细计算过程 ==={Style.RESET_ALL}")
        if result.calculation_details:
            if 'margin_calculation' in result.calculation_details:
                margin_calc = result.calculation_details['margin_calculation']
                print(f"毛利率计算：")
                print(f"  售价：¥{margin_calc.get('selling_price', 'N/A')}")
                print(f"  总成本：¥{margin_calc.get('total_cost', 'N/A')}")
                print(f"  利润：¥{margin_calc.get('profit', 'N/A')}")
                print(f"  公式：{margin_calc.get('formula', 'N/A')}")
            
            if 'price_red_lines' in result.calculation_details:
                price_lines = result.calculation_details['price_red_lines']
                print(f"\n价格红线计算：")
                print(f"  总成本：¥{price_lines.get('total_cost', 'N/A')}")
                print(f"  盈亏平衡价：¥{price_lines.get('break_even_price', 'N/A')}")
                print(f"  最低安全价：¥{price_lines.get('min_safe_price', 'N/A')}")
                for formula_name, formula in price_lines.get('formulas', {}).items():
                    print(f"  {formula_name}: {formula}")
            
            if 'risk_assessment' in result.calculation_details:
                risk_assess = result.calculation_details['risk_assessment']
                print(f"\n风险评估计算：")
                print(f"  利润风险：{risk_assess.get('profit_risk', 'N/A')}")
                print(f"  库存风险：{risk_assess.get('inventory_risk', 'N/A')}")
                print(f"  现金流风险：{risk_assess.get('cash_flow_risk', 'N/A')}")
                print(f"  合规风险：{risk_assess.get('compliance_risk', 'N/A')}")
                print(f"  公式：{risk_assess.get('formula', 'N/A')}")
        
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
    print(f"{Fore.GREEN}RiskControlAgent 功能测试{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    test_cases = [
        (create_test_request_1(), "健康商品（利润充足，风险低）"),
        (create_test_request_2(), "高风险商品（利润微薄，库存积压）"),
        (create_test_request_3(), "品牌控价商品（有限价约束）"),
        (create_test_request_4(), "接近盈亏平衡点（利润极薄）"),
    ]
    
    results = {}
    
    for request, name in test_cases:
        results[name] = test_risk_control_agent(request, name)
    
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
        print_success("🎉 所有测试通过！RiskControlAgent 功能正常！")
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
