from decimal import Decimal

from sqlalchemy.orm import Session

from app.repos.product_repo import ProductRepo
from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.utils.math_utils import money, ratio


class ContextService:
    def __init__(self, db: Session):
        self.product_repo = ProductRepo(db)

    def load_product_context(self, product_id: int) -> ProductContext:
        product = self.product_repo.get_product(product_id)
        if product is None:
            raise ValueError(f"product not found: {product_id}")

        return ProductContext(
            productId=product.id,
            shopId=product.shop_id,
            productName=product.product_name or f"商品{product.id}",
            categoryName=product.category_name,
            currentPrice=money(product.sale_price),
            costPrice=money(product.cost_price),
            stock=max(int(product.stock or 0), 0),
        )

    def load_daily_metrics(self, product_id: int, limit: int = 30) -> list[DailyMetricSnapshot]:
        rows = self.product_repo.list_daily_metrics(product_id, limit=limit)
        return [
            DailyMetricSnapshot(
                statDate=row.stat_date,
                visitorCount=max(int(row.visitor_count or 0), 0),
                addCartCount=max(int(row.add_cart_count or 0), 0),
                payBuyerCount=max(int(row.pay_buyer_count or 0), 0),
                salesCount=max(int(row.pay_item_qty or 0), 0),
                turnover=money(row.pay_amount),
                conversionRate=ratio(row.convert_rate),
            )
            for row in rows
        ]

    def load_traffic(self, product_id: int, limit: int = 30) -> list[TrafficSnapshot]:
        rows = self.product_repo.list_traffic(product_id, limit=limit)
        return [
            TrafficSnapshot(
                statDate=row.stat_date,
                trafficSource=row.traffic_source,
                impressionCount=max(int(row.impression_count or 0), 0),
                clickCount=max(int(row.click_count or 0), 0),
                visitorCount=max(int(row.visitor_count or 0), 0),
                payAmount=money(row.pay_amount),
                roi=ratio(row.roi),
            )
            for row in rows
        ]

    @staticmethod
    def infer_baseline_sales(metrics: list[DailyMetricSnapshot], stock: int) -> int:
        if metrics:
            return max(sum(item.sales_count for item in metrics), 30)
        return max(stock // 3, 30)

    @staticmethod
    def infer_baseline_profit(current_price: Decimal, cost_price: Decimal, monthly_sales: int) -> Decimal:
        return money((money(current_price) - money(cost_price)) * Decimal(max(monthly_sales, 0)))

