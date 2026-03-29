from decimal import Decimal

from app.schemas.agent import DataAgentOutput, DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.tools.outlier_clean_tool import OutlierCleanTool
from app.tools.product_data_tool import ProductDataTool
from app.utils.math_utils import money


class DataAnalysisAgent:
    code = "DATA_ANALYSIS"
    name = "数据分析Agent"

    def __init__(self) -> None:
        self.data_tool = ProductDataTool()
        self.clean_tool = OutlierCleanTool()
        self.elasticity_tool = ElasticityProfitTool()

    def run(
        self,
        product: ProductContext,
        metrics: list[DailyMetricSnapshot],
        traffic: list[TrafficSnapshot],
        strategy_goal: str,
    ) -> DataAgentOutput:
        summary = self.data_tool.summarize(product=product, metrics=metrics, traffic=traffic)
        monthly_sales = int(summary["monthly_sales"])

        sales_series = [item.sales_count for item in metrics]
        cleaned_sales = self.clean_tool.winsorize(sales_series)
        trend_score = 0.0
        if len(cleaned_sales) >= 8:
            recent = sum(cleaned_sales[-7:]) / 7
            prev = sum(cleaned_sales[-14:-7]) / 7 if len(cleaned_sales) >= 14 else recent
            if prev > 0:
                trend_score = (recent - prev) / prev

        current_price = money(product.current_price)
        if strategy_goal.upper() == "CLEARANCE":
            suggested = money(current_price * Decimal("0.95"))
        elif strategy_goal.upper() == "MARKET_SHARE":
            suggested = money(current_price * Decimal("0.97"))
        else:
            suggested = money(current_price * (Decimal("1.04") if trend_score > 0.06 else Decimal("1.01")))

        expected_sales = self.elasticity_tool.estimate_sales(monthly_sales, current_price, suggested, strategy_goal)
        expected_profit = self.elasticity_tool.estimate_profit(suggested, money(product.cost_price), expected_sales)
        floor = money(max(money(product.cost_price) * Decimal("1.08"), suggested * Decimal("0.94")))
        ceiling = money(suggested * Decimal("1.08"))
        confidence = 0.78 if metrics else 0.62

        return DataAgentOutput(
            suggestedPrice=suggested,
            suggestedMinPrice=floor,
            suggestedMaxPrice=ceiling,
            expectedSales=expected_sales,
            expectedProfit=expected_profit,
            confidence=confidence,
            summary=(
                f"基于近30天经营数据，建议价格 {suggested}，预计销量 {expected_sales}，"
                f"预计利润 {expected_profit}，趋势评分 {trend_score:.2f}。"
            ),
        )
