from typing import Any

from sqlalchemy import asc, delete, desc, func, select
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
        stage: str = "completed",
        run_attempt: int = 0,
        raw_output: dict[str, Any] | None = None,
    ) -> AgentRunLog:
        """写入 Agent 卡片日志，兼容旧字段 thought_content/speak_order。

        raw_output: Pydantic 校验后的完整 JSON（camelCase），供失败重试时回放下游 context。
        与 suggestion 不同——suggestion 是裁剪后的展示卡片，raw_output 保留全部字段。
        """
        order = int(display_order or self.get_next_display_order(task_id))
        normalized_stage = "failed" if str(stage or "").strip().lower() == "failed" else "completed"
        log = AgentRunLog(
            task_id=task_id,
            role_name=(agent_name or "Agent").strip() or "Agent",
            speak_order=order,
            thought_content=thinking_summary,
            thinking_summary=thinking_summary,
            evidence_json=evidence or [],
            suggestion_json=suggestion or {},
            raw_output_json=raw_output if isinstance(raw_output, dict) and raw_output else None,
            final_reason=reason_why,
            display_order=order,
            stage=normalized_stage,
            run_attempt=max(int(run_attempt or 0), 0),
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
        run_attempt: int = 0,
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
            run_attempt=max(int(run_attempt or 0), 0),
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
                asc(AgentRunLog.run_attempt),
                asc(func.coalesce(AgentRunLog.display_order, AgentRunLog.speak_order, 999)),
                asc(AgentRunLog.id),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def delete_running_and_failed_by_task_id(self, task_id: int) -> int:
        result = self.db.execute(
            delete(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .where(AgentRunLog.stage.in_(("running", "failed")))
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def delete_running_and_failed_by_run_attempt(self, task_id: int, run_attempt: int) -> int:
        """只删除指定 run_attempt 下的 running/failed 占位卡片，保留已完成（completed）的卡片。

        这是部分重试的关键：新一轮 retry 前只清理本轮的失败/占位，不触碰上一轮已成功的 Agent 记录。
        """
        result = self.db.execute(
            delete(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .where(AgentRunLog.run_attempt == int(run_attempt))
            .where(AgentRunLog.stage.in_(("running", "failed")))
        )
        self.db.commit()
        return int(result.rowcount or 0)

    def list_completed_raw_outputs(self, task_id: int) -> dict[int, dict[str, Any]]:
        """返回已完成 Agent 的 raw_output_json，按 display_order 聚合。

        同一 display_order 若存在多轮 completed 记录（理论上不会，但历史数据可能），
        保留最新 run_attempt 的那条。raw_output_json 为空的记录视作无效（会触发断点回退到该 order）。

        返回 {display_order: raw_output_dict}，只含可用于回放的条目。
        """
        stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .where(AgentRunLog.stage == "completed")
            .order_by(
                desc(AgentRunLog.run_attempt),
                desc(AgentRunLog.id),
            )
        )
        result: dict[int, dict[str, Any]] = {}
        for row in self.db.scalars(stmt).all():
            order = int(row.display_order or row.speak_order or 0)
            if order <= 0 or order in result:
                continue
            raw = row.raw_output_json
            if not isinstance(raw, dict) or not raw:
                continue
            result[order] = raw
        return result

    def list_latest_by_task_id(self, task_id: int, limit: int = 200) -> list[AgentRunLog]:
        stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .order_by(
                desc(AgentRunLog.run_attempt),
                desc(func.coalesce(AgentRunLog.display_order, AgentRunLog.speak_order, 0)),
                desc(AgentRunLog.id),
            )
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
