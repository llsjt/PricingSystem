from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Integer, String, Text, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingResult(Base):
    __tablename__ = "pricing_result"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    final_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    expected_sales: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_profit: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    profit_growth: Mapped[Decimal] = mapped_column(DECIMAL(12, 2), nullable=False, default=0)
    is_pass: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    execute_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), server_onupdate=text("CURRENT_TIMESTAMP")
    )

