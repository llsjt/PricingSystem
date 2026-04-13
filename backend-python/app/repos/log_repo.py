from typing import Any

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.models.agent_run_log import AgentRunLog


class LogRepo:
    """Agent 日志仓储：写入 running 占位卡片和 completed 完整卡片。"""

    def __init__(self, db: Session):
        self.db = db

    def get_next_display_order(self, task_id: int) -> int:
        stmt = select(func.max(AgentRunLog.display_order)).where(AgentRunLog.task_id == task_id)
        value = self.db.scalar(stmt)
        if value is not None:
            return int(value) + 1
        return self.get_next_speak_order(task_id)

    def get_next_speak_order(self, task_id: int) -> int:
        stmt = select(func.max(AgentRunLog.speak_order)).where(AgentRunLog.task_id == task_id)
        value = self.db.scalar(stmt)
        return int(value or 0) + 1

    def append_card(
        self,
        task_id: int,
        agent_name: str,
        display_order: int,
        thinking_summary: str,
        evidence: list[dict[str, Any]],
        suggestion: dict[str, Any],
        reason_why: str | None = None,
    ) -> AgentRunLog:
        """写入 Agent 卡片日志，兼容旧字段 thought_content/speak_order。"""
        order = int(display_order or self.get_next_display_order(task_id))
        log = AgentRunLog(
            task_id=task_id,
            role_name=(agent_name or "Agent").strip() or "Agent",
            speak_order=order,
            thought_content=thinking_summary,
            thinking_summary=thinking_summary,
            evidence_json=evidence or [],
            suggestion_json=suggestion or {},
            final_reason=reason_why,
            display_order=order,
            stage="completed",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def append_running_card(
        self,
        task_id: int,
        agent_name: str,
        display_order: int,
    ) -> AgentRunLog:
        """写入 running 占位卡片，表示 Agent 正在工作。"""
        order = int(display_order or self.get_next_display_order(task_id))
        log = AgentRunLog(
            task_id=task_id,
            role_name=(agent_name or "Agent").strip() or "Agent",
            speak_order=order,
            thought_content=None,
            thinking_summary=None,
            evidence_json=[],
            suggestion_json={},
            final_reason=None,
            display_order=order,
            stage="running",
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_by_task_id(self, task_id: int, limit: int = 200) -> list[AgentRunLog]:
        stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .order_by(
                asc(func.coalesce(AgentRunLog.display_order, AgentRunLog.speak_order, 999)),
                asc(AgentRunLog.id),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def list_latest_by_task_id(self, task_id: int, limit: int = 200) -> list[AgentRunLog]:
        stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .order_by(desc(func.coalesce(AgentRunLog.display_order, AgentRunLog.speak_order, 0)), desc(AgentRunLog.id))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
