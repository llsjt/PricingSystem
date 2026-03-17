"""
MarketIntelAgent 单元测试
测试重构后的市场情报 Agent 功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.market_intel_agent import MarketIntelAgent
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

def create_test_request_1():
    """测试用例 1：竞争激烈市场（多个竞品，价格战）"""
    return AnalysisRequest(
        task_id="TEST_MI_001",
        product=ProductBase(
            product_id="P001",
            product_name="蓝牙耳机 X1",
            category="数码",
            sub_category="蓝牙耳机",
            current_price=99.0,
            cost=50.0,
            original_price=129.0,
            stock=500,
            is_new_product=False,
            is_seasonal=False
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=89.0, sales_volume=5000, rating=4.5, review_count=1200, promotion_tags=["降价", "满减"]),
                CompetitorInfo(competitor_id="C002", product_name="竞品 B", current_price=95.0, sales_volume=4500, rating=4.3, review_count=980, promotion_tags=["促销"]),
                CompetitorInfo(competitor_id="C003", product_name="竞品 C", current_price=79.0, sales_volume=6000, rating=4.2, review_count=1500, promotion_tags=["打折", "秒杀"]),
                CompetitorInfo(competitor_id="C004", product_name="竞品 D", current_price=109.0, sales_volume=3000, rating=4.7, review_count=800, promotion_tags=[]),
                CompetitorInfo(competitor_id="C005", product_name="竞品 E", current_price=92.0, sales_volume=4800, rating=4.4, review_count=1100, promotion_tags=["优惠"]),
            ],
            category_total_sales=50000,
            top_3_brand_share=0.45
        ),
        risk_data=RiskData(),
        customer_reviews=[
            ReviewData(rating=5, content="音质很好，性价比高，物流快", tags=["音质好", "性价比高"]),
            ReviewData(rating=4, content="不错，就是包装有点简陋", tags=["包装差"]),
            ReviewData(rating=5, content="非常满意，推荐购买", tags=["推荐"]),
            ReviewData(rating=3, content="一般般，价格有点贵", tags=["贵"]),
            ReviewData(rating=5, content="good quality, love it", tags=["quality"]),
        ],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_2():
    """测试用例 2：蓝海市场（无竞品）"""
    return AnalysisRequest(
        task_id="TEST_MI_002",
        product=ProductBase(
            product_id="P002",
            product_name="创新产品 Z1",
            category="数码",
            current_price=199.0,
            cost=80.0,
            stock=200,
            is_new_product=True,
            is_seasonal=False
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(
            competitors=[],
            category_total_sales=10000
        ),
        risk_data=RiskData(),
        customer_reviews=[
            ReviewData(rating=5, content="全新体验，非常棒", tags=["创新"]),
            ReviewData(rating=4, content="不错，但价格偏高", tags=["贵"]),
        ],
        strategy_goal="MARKET_SHARE"
    )

def create_test_request_3():
    """测试用例 3：负面舆情（口碑差）"""
    return AnalysisRequest(
        task_id="TEST_MI_003",
        product=ProductBase(
            product_id="P003",
            product_name="问题商品",
            category="服装",
            current_price=79.0,
            cost=35.0,
            stock=1000
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=85.0, rating=4.5),
                CompetitorInfo(competitor_id="C002", product_name="竞品 B", current_price=89.0, rating=4.6),
            ]
        ),
        risk_data=RiskData(),
        customer_reviews=[
            ReviewData(rating=1, content="质量太差，烂透了", tags=["质量差", "差评"]),
            ReviewData(rating=2, content="物流慢，客服态度差", tags=["物流慢", "客服差"]),
            ReviewData(rating=1, content="假货，失望", tags=["假货", "失望"]),
            ReviewData(rating=2, content="broken, defective", tags=["broken"]),
            ReviewData(rating=3, content="一般", tags=[]),
        ],
        strategy_goal="MAX_PROFIT"
    )

def create_test_request_4():
    """测试用例 4：高端定位（价格最高但口碑好）"""
    return AnalysisRequest(
        task_id="TEST_MI_004",
        product=ProductBase(
            product_id="P004",
            product_name="高端旗舰",
            category="数码",
            current_price=299.0,
            cost=150.0,
            stock=300,
            is_new_product=False
        ),
        sales_data=SalesData(),
        competitor_data=CompetitorData(
            competitors=[
                CompetitorInfo(competitor_id="C001", product_name="竞品 A", current_price=199.0, rating=4.3),
                CompetitorInfo(competitor_id="C002", product_name="竞品 B", current_price=229.0, rating=4.4),
                CompetitorInfo(competitor_id="C003", product_name="竞品 C", current_price=179.0, rating=4.2),
            ],
            upcoming_platform_events=[{"name": "618", "start_date": "2024-06-01", "required_discount": 0.85}]
        ),
        risk_data=RiskData(),
        customer_reviews=[
            ReviewData(rating=5, content="一分钱一分货，质量优秀", tags=["质量好", "优秀"]),
            ReviewData(rating=5, content="高端大气，值得购买", tags=["高端", "推荐"]),
            ReviewData(rating=4, content="很好，就是价格贵", tags=["贵"]),
        ],
        strategy_goal="MAX_PROFIT"
    )

def test_market_intel_agent(test_request: AnalysisRequest, test_name: str):
    """测试单个用例"""
    print_section(f"测试：{test_name}")
    
    try:
        agent = MarketIntelAgent()
        
        print_info(f"任务 ID: {test_request.task_id}")
        print_info(f"商品：{test_request.product.product_name}")
        print_info(f"价格：¥{test_request.product.current_price}")
        print_info(f"竞品数量：{len(test_request.competitor_data.competitors)}")
        print_info(f"评论数量：{len(test_request.customer_reviews)}")
        print_info(f"战略目标：{test_request.strategy_goal}")
        
        # 执行分析
        print(f"\n{Fore.YELLOW}正在执行市场情报分析...{Style.RESET_ALL}\n")
        result = agent.analyze(test_request)
        
        # 输出结果
        print(f"{Fore.GREEN}=== 竞争格局 ==={Style.RESET_ALL}")
        print(f"✓ 竞争强度：{result.competition_level} (得分：{result.competition_score:.2f})")
        print(f"✓ 价格定位：{result.price_position} (分位数：{result.price_percentile:.2f})")
        
        if result.avg_competitor_price:
            print(f"✓ 竞品均价：¥{result.avg_competitor_price:.2f}")
            print(f"✓ 与均价差距：{result.price_gap_vs_avg:.1%}")
        
        if result.min_competitor_price:
            print(f"✓ 竞品价格区间：¥{result.min_competitor_price:.2f} - ¥{result.max_competitor_price:.2f}")
        
        if result.active_competitor_promotions:
            print(f"\n⚠ 竞品促销活动 ({len(result.active_competitor_promotions)}个)：")
            for promo in result.active_competitor_promotions[:3]:
                print(f"  - {promo['competitor_name']}: {', '.join(promo['promotion_tags'])}")
        
        print(f"\n{Fore.CYAN}=== 消费者情感 ==={Style.RESET_ALL}")
        print(f"✓ 情感得分：{result.sentiment_score:.2f}")
        print(f"✓ 情感标签：{result.sentiment_label}")
        
        if result.top_positive_keywords:
            print(f"✓ 正面关键词：{', '.join(result.top_positive_keywords[:5])}")
        
        if result.top_negative_keywords:
            print(f"✓ 负面关键词：{', '.join(result.top_negative_keywords[:5])}")
        
        if result.estimated_market_share:
            print(f"\n✓ 估算市场份额：{result.estimated_market_share:.2%}")
            print(f"✓ 份额趋势：{result.market_share_trend}")
        
        print(f"\n{Fore.YELLOW}=== 市场建议 ==={Style.RESET_ALL}")
        print(f"建议策略：{result.market_suggestion}")
        print(f"建议置信度：{result.suggestion_confidence:.1%}")
        
        print(f"\n理由：")
        for i, reason in enumerate(result.suggestion_reasons, 1):
            print(f"  {i}. {reason}")
        
        print(f"\n{Fore.BLUE}=== 数据来源 ==={Style.RESET_ALL}")
        for source in result.data_sources:
            print(f"  - {source}")
        
        if result.limitations:
            print(f"\n{Fore.MAGENTA}局限性说明：{Style.RESET_ALL}")
            for i, limit in enumerate(result.limitations, 1):
                print(f"  {i}. {limit}")
        
        print(f"\n{Fore.GREEN}=== 详细分析 ==={Style.RESET_ALL}")
        if result.analysis_details:
            if 'price_position_analysis' in result.analysis_details:
                price_analysis = result.analysis_details['price_position_analysis']
                print(f"价格定位分析：")
                print(f"  当前价格：¥{price_analysis.get('current_price', 'N/A')}")
                print(f"  竞品均价：¥{price_analysis.get('avg_competitor_price', 'N/A')}")
                percentile = price_analysis.get('percentile', 'N/A')
                if isinstance(percentile, float):
                    print(f"  分位数：{percentile:.2f}")
                else:
                    print(f"  分位数：{percentile}")
                print(f"  公式：{price_analysis.get('formula', 'N/A')}")
            
            if 'competition_analysis' in result.analysis_details:
                comp_analysis = result.analysis_details['competition_analysis']
                print(f"\n竞争强度分析：")
                print(f"  竞品数量得分：{comp_analysis.get('num_score', 'N/A')}")
                print(f"  市场集中度得分：{comp_analysis.get('concentration_score', 'N/A')}")
                print(f"  促销得分：{comp_analysis.get('promo_score', 'N/A')}")
                print(f"  总得分：{comp_analysis.get('total_score', 'N/A')}")
                print(f"  公式：{comp_analysis.get('formula', 'N/A')}")
        
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
    print(f"{Fore.GREEN}MarketIntelAgent 功能测试{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    
    test_cases = [
        (create_test_request_1(), "竞争激烈市场（多个竞品，价格战）"),
        (create_test_request_2(), "蓝海市场（无竞品）"),
        (create_test_request_3(), "负面舆情（口碑差）"),
        (create_test_request_4(), "高端定位（价格最高但口碑好）"),
    ]
    
    results = {}
    
    for request, name in test_cases:
        results[name] = test_market_intel_agent(request, name)
    
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
        print_success("🎉 所有测试通过！MarketIntelAgent 功能正常！")
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
