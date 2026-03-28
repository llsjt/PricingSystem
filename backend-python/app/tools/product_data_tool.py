from decimal import Decimal

from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.utils.math_utils import money


class ProductDataTool:
    def summarize(
        self,
        product: ProductContext,
        metrics: list[DailyMetricSnapshot],
        traffic: list[TrafficSnapshot],
    ) -> dict:
        monthly_sales = sum(item.sales_count for item in metrics)
        monthly_turnover = money(sum(item.turnover for item in metrics) if metrics else 0)
        avg_conversion = (
            sum((item.conversion_rate for item in metrics), Decimal("0.0000")) / Decimal(max(len(metrics), 1))
        )
        total_visitors = sum(item.visitor_count for item in metrics)
        total_clicks = sum(item.click_count for item in traffic)
        total_impressions = sum(item.impression_count for item in traffic)
        ctr = Decimal("0.0000")
        if total_impressions > 0:
            ctr = Decimal(total_clicks) / Decimal(total_impressions)

        return {
            "product_id": product.product_id,
            "current_price": money(product.current_price),
            "cost_price": money(product.cost_price),
            "stock": product.stock,
            "monthly_sales": monthly_sales,
            "monthly_turnover": monthly_turnover,
            "average_conversion_rate": avg_conversion.quantize(Decimal("0.0000")),
            "total_visitors": total_visitors,
            "traffic_ctr": ctr.quantize(Decimal("0.0000")),
        }

