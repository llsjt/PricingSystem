"""商品日指标模型，对应商品的日粒度经营数据。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductDailyMetric(Base):
    __tablename__ = "product_daily_metric"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    visitor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    add_cart_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pay_buyer_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pay_item_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pay_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    refund_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    convert_rate: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 4), nullable=True, default=0)
    upload_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
