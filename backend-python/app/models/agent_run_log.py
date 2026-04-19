from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentRunLog(Base):
    __tablename__ = "agent_run_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    role_name: Mapped[str] = mapped_column(String(50), nullable=False)
    speak_order: Mapped[int] = mapped_column(Integer, nullable=False)
    thought_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    suggestion_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    final_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'completed'"))
    run_attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
