"""流量与促销日指标模型，对应外部导入的流量促销数据。"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrafficPromoDaily(Base):
    __tablename__ = "traffic_promo_daily"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    traffic_source: Mapped[str] = mapped_column(String(50), nullable=False)
    impression_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    click_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    visitor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cost_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    pay_amount: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    roi: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 4), nullable=True, default=0)
    upload_batch_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
