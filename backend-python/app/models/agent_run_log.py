from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, text
from sqlalchemy.dialects.mysql import DECIMAL
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentRunLog(Base):
    __tablename__ = "agent_run_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    agent_code: Mapped[str] = mapped_column(String(30), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    run_order: Mapped[int] = mapped_column(Integer, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    suggested_price: Mapped[Decimal | None] = mapped_column(DECIMAL(10, 2), nullable=True)
    predicted_profit: Mapped[Decimal | None] = mapped_column(DECIMAL(12, 2), nullable=True)
    confidence_score: Mapped[Decimal | None] = mapped_column(DECIMAL(8, 4), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    need_manual_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

