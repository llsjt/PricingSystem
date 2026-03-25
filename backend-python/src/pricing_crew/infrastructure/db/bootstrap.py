"""数据库初始化与演示业务数据灌入模块。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Iterable, List

from sqlalchemy import func
from sqlalchemy.orm import Session

from pricing_crew.infrastructure.db.database import Base, SessionLocal, engine
from pricing_crew.infrastructure.db.models import BizProduct, BizPromotionHistory, BizSalesDaily


@dataclass(frozen=True)
class SeedProduct:
    title: str
    category: str
    cost_price: Decimal
    market_price: Decimal
    current_price: Decimal
    stock: int
    monthly_sales: int
    click_rate: Decimal
    conversion_rate: Decimal
    trend: str
    base_daily_sales: int
    amplitude: int


SEED_PRODUCTS: List[SeedProduct] = [
    SeedProduct(
        title="旗舰降噪蓝牙耳机",
        category="数码配件",
        cost_price=Decimal("149.00"),
        market_price=Decimal("299.00"),
        current_price=Decimal("219.00"),
        stock=260,
        monthly_sales=312,
        click_rate=Decimal("0.0860"),
        conversion_rate=Decimal("0.0410"),
        trend="declining",
        base_daily_sales=11,
        amplitude=3,
    ),
    SeedProduct(
        title="316不锈钢保温杯 750ml",
        category="家居用品",
        cost_price=Decimal("28.00"),
        market_price=Decimal("89.00"),
        current_price=Decimal("59.00"),
        stock=480,
        monthly_sales=620,
        click_rate=Decimal("0.0710"),
        conversion_rate=Decimal("0.0550"),
        trend="stable",
        base_daily_sales=21,
        amplitude=4,
    ),
    SeedProduct(
        title="UPF50+ 轻量防晒衣",
        category="户外服饰",
        cost_price=Decimal("68.00"),
        market_price=Decimal("169.00"),
        current_price=Decimal("139.00"),
        stock=380,
        monthly_sales=228,
        click_rate=Decimal("0.0930"),
        conversion_rate=Decimal("0.0360"),
        trend="rising",
        base_daily_sales=8,
        amplitude=5,
    ),
]


def _sales_series(seed: SeedProduct, days: int = 90) -> Iterable[tuple[date, int, Decimal]]:
    today = datetime.utcnow().date()
    for offset in range(days):
        stat_date = today - timedelta(days=days - offset - 1)
        weekday_factor = 1.12 if stat_date.weekday() in {4, 5} else 0.95 if stat_date.weekday() == 0 else 1.0
        seasonal_factor = 1.0
        if seed.category == "户外服饰":
            seasonal_factor = 0.82 + offset / max(days, 1) * 0.42
        elif seed.category == "数码配件":
            seasonal_factor = 1.08 - offset / max(days, 1) * 0.18

        trend_bias = 0.0
        if seed.trend == "declining":
            trend_bias = (days - offset) / days * 2.2
        elif seed.trend == "rising":
            trend_bias = offset / days * 2.4

        raw_sales = (seed.base_daily_sales + (offset % 7 - 3) * 0.35 + seed.amplitude * 0.12 + trend_bias) * weekday_factor * seasonal_factor
        daily_sales = max(2, int(round(raw_sales)))
        discount_factor = Decimal("0.97") if seed.trend == "declining" and offset % 14 in {5, 6} else Decimal("1.00")
        daily_revenue = (seed.current_price * discount_factor * Decimal(daily_sales)).quantize(Decimal("0.01"))
        yield stat_date, daily_sales, daily_revenue


def _next_id(db: Session, model) -> int:
    max_id = db.query(func.max(model.id)).scalar()
    return int(max_id or 0) + 1


def _upsert_seed_product(db: Session, seed: SeedProduct) -> BizProduct:
    product = db.query(BizProduct).filter(BizProduct.title == seed.title, BizProduct.source == "SEED_REALISTIC").first()
    if product is None:
        product = BizProduct(id=_next_id(db, BizProduct), title=seed.title, source="SEED_REALISTIC")
        db.add(product)

    product.category = seed.category
    product.cost_price = seed.cost_price
    product.market_price = seed.market_price
    product.current_price = seed.current_price
    product.stock = seed.stock
    product.monthly_sales = seed.monthly_sales
    product.click_rate = seed.click_rate
    product.conversion_rate = seed.conversion_rate
    product.updated_at = datetime.utcnow()
    return product


def _refresh_sales_rows(db: Session, product_id: int, seed: SeedProduct) -> None:
    db.query(BizSalesDaily).filter(BizSalesDaily.product_id == product_id).delete(synchronize_session=False)
    next_id = _next_id(db, BizSalesDaily)
    for stat_date, daily_sales, daily_revenue in _sales_series(seed):
        db.add(
            BizSalesDaily(
                id=next_id,
                product_id=product_id,
                stat_date=stat_date,
                daily_sales=daily_sales,
                daily_revenue=daily_revenue,
            )
        )
        next_id += 1


def _refresh_promotion_rows(db: Session, product_id: int, seed: SeedProduct) -> None:
    db.query(BizPromotionHistory).filter(BizPromotionHistory.product_id == product_id).delete(synchronize_session=False)
    if seed.category != "数码配件":
        return

    db.add(
        BizPromotionHistory(
            id=_next_id(db, BizPromotionHistory),
            product_id=product_id,
            promotion_name="周末满减",
            promotion_type="满减",
            start_date=datetime.utcnow().date() - timedelta(days=21),
            end_date=datetime.utcnow().date() - timedelta(days=19),
            discount_rate=Decimal("0.9500"),
            discount_price=Decimal("208.05"),
            sales_before=10,
            sales_during=15,
            sales_lift=Decimal("0.5000"),
        )
    )


def init_database() -> None:
    Base.metadata.create_all(bind=engine)


def seed_realistic_demo_data() -> None:
    db = SessionLocal()
    try:
        for seed in SEED_PRODUCTS:
            product = _upsert_seed_product(db, seed)
            db.flush()
            _refresh_sales_rows(db, product.id, seed)
            _refresh_promotion_rows(db, product.id, seed)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def seeded_product_count() -> int:
    db = SessionLocal()
    try:
        return int(
            db.query(func.count(BizProduct.id))
            .filter(BizProduct.source == "SEED_REALISTIC")
            .scalar()
            or 0
        )
    finally:
        db.close()
