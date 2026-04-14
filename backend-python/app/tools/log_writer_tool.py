from typing import Any

from sqlalchemy.orm import Session

from app.repos.log_repo import LogRepo
from app.repos.task_repo import TaskRepo


class LogWriterTool:
    """统一日志写入工具：写入 Agent 进度占位和完整卡片。"""

    def __init__(self, db: Session):
        self.log_repo = LogRepo(db)
        self.task_repo = TaskRepo(db)

    def write_agent_card(
        self,
        task_id: int,
        agent_name: str,
        display_order: int,
        thinking_summary: str,
        evidence: list[dict[str, Any]],
        suggestion: dict[str, Any],
        reason_why: str | None = None,
        stage: str = "completed",
    ) -> None:
        task = self.task_repo.get_by_id(task_id)
        if task is None or str(task.task_status or "").upper() == "CANCELLED":
            return

        self.log_repo.append_card(
            task_id=task_id,
            agent_name=agent_name,
            display_order=display_order,
            thinking_summary=thinking_summary,
            evidence=evidence,
            suggestion=suggestion,
            reason_why=reason_why,
            stage=stage,
        )

    def write_running_card(
        self,
        task_id: int,
        agent_name: str,
        display_order: int,
    ) -> None:
        task = self.task_repo.get_by_id(task_id)
        if task is None or str(task.task_status or "").upper() == "CANCELLED":
            return

        self.log_repo.append_running_card(
            task_id=task_id,
            agent_name=agent_name,
            display_order=display_order,
        )
