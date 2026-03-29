from typing import Any

from sqlalchemy.orm import Session

from app.repos.log_repo import LogRepo


class LogWriterTool:
    """统一日志写入工具：MVP 只写 Agent 卡片。"""

    def __init__(self, db: Session):
        self.log_repo = LogRepo(db)

    def write_agent_card(
        self,
        task_id: int,
        agent_name: str,
        display_order: int,
        thinking_summary: str,
        evidence: list[dict[str, Any]],
        suggestion: dict[str, Any],
        reason_why: str | None = None,
    ) -> None:
        self.log_repo.append_card(
            task_id=task_id,
            agent_name=agent_name,
            display_order=display_order,
            thinking_summary=thinking_summary,
            evidence=evidence,
            suggestion=suggestion,
            reason_why=reason_why,
        )
