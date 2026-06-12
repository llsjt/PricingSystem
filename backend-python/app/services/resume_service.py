"""Agent 级断点续跑计划服务。"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.repos.log_repo import LogRepo
from app.crew.protocols import CrewRunPayload
from app.services.resume_fingerprint import build_resume_meta


ANALYSIS_ORDERS = [1, 2, 3]
MANAGER_ORDER = 4


@dataclass(frozen=True)
class ResumePlan:
    prior_outputs: dict[int, dict[str, Any]]
    analysis_orders_to_run: list[int]
    manager_completed: bool
    should_run_manager_now: bool
    all_done: bool


class ResumeService:
    """根据历史成功卡片决定本轮需要补跑哪些 Agent。"""

    def __init__(self, db: Session):
        self.log_repo = LogRepo(db)

    def compute_resume_plan(self, task_id: int, payload: CrewRunPayload | None = None) -> ResumePlan:
        expected_meta = build_resume_meta(payload) if payload is not None else None
        completed_rows = self.log_repo.list_completed_raw_outputs(task_id, expected_resume_meta=expected_meta)
        analysis_orders_to_run = [order for order in ANALYSIS_ORDERS if order not in completed_rows]
        manager_completed = MANAGER_ORDER in completed_rows and not analysis_orders_to_run
        should_run_manager_now = not analysis_orders_to_run and not manager_completed

        return ResumePlan(
            prior_outputs=completed_rows,
            analysis_orders_to_run=analysis_orders_to_run,
            manager_completed=manager_completed,
            should_run_manager_now=should_run_manager_now,
            all_done=manager_completed,
        )
