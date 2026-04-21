"""商品仓储模块，封装商品与商品指标相关的数据库读取逻辑。"""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_daily_metric import ProductDailyMetric
from app.models.product_sku import ProductSku
from app.models.traffic_promo_daily import TrafficPromoDaily


class ProductRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_product(self, product_id: int) -> Product | None:
        return self.db.get(Product, product_id)

    def list_skus(self, product_id: int) -> list[ProductSku]:
        stmt = (
            select(ProductSku)
            .where(ProductSku.product_id == product_id)
            .order_by(desc(ProductSku.updated_at), desc(ProductSku.id))
        )
        return list(self.db.scalars(stmt).all())

    def list_daily_metrics(self, product_id: int, limit: int = 30) -> list[ProductDailyMetric]:
        stmt = (
            select(ProductDailyMetric)
            .where(ProductDailyMetric.product_id == product_id)
            .order_by(desc(ProductDailyMetric.stat_date), desc(ProductDailyMetric.id))
            .limit(limit)
        )
        return list(reversed(list(self.db.scalars(stmt).all())))

    def list_traffic(self, product_id: int, limit: int = 30) -> list[TrafficPromoDaily]:
        stmt = (
            select(TrafficPromoDaily)
            .where(TrafficPromoDaily.product_id == product_id)
            .order_by(desc(TrafficPromoDaily.stat_date), desc(TrafficPromoDaily.id))
            .limit(limit)
        )
        return list(reversed(list(self.db.scalars(stmt).all())))
