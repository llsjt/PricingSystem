from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, String, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingTask(Base):
    __tablename__ = "pricing_task"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_code: Mapped[str] = mapped_column(String(50), nullable=False)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sku_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, default=0)
    baseline_profit: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    suggested_min_price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    suggested_max_price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    task_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", server_default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

