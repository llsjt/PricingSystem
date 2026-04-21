"""商品模型，对应商品主数据表。"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, String, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shop_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    external_product_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sub_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    primary_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secondary_category_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sale_price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    cost_price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN", server_default="UNKNOWN")
    profile_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="COMPLETE", server_default="COMPLETE"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )
