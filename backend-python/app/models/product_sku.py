from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, String, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductSku(Base):
    __tablename__ = "product_sku"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    external_sku_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sku_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sku_attr: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sale_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    cost_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

