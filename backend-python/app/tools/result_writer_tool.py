"""结果写入工具，负责把最终定价结果持久化到数据库。"""

from sqlalchemy.orm import Session

from app.domain.final_decision_verifier import VerificationResult
from app.repos.result_repo import ResultRepo
from app.repos.task_repo import TaskRepo
from app.schemas.result import TaskFinalResult
from app.services.result_finalization_service import ResultFinalizationService
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY


class ResultWriterTool:
    def __init__(self, db: Session, execution_id: str | None = None):
        self.result_repo = ResultRepo(db)
        self.task_repo = TaskRepo(db)
        self.finalization_service = ResultFinalizationService(db)
        self.execution_id = execution_id
        self._verification_result: VerificationResult | None = None

    def set_verification_result(self, verification: VerificationResult | None) -> None:
        self._verification_result = verification

    def write_final_result(self, payload: TaskFinalResult) -> None:
        task = self.task_repo.get_by_id(payload.task_id)
        if task is None:
            raise ValueError(f"task not found: {payload.task_id}")
        if str(task.task_status or "").upper() == "CANCELLED":
            return

        execute_strategy = MANUAL_REVIEW_STRATEGY
        review_required = True

        if self.execution_id:
            self.finalization_service.finalize_manual_review(
                payload,
                execution_id=self.execution_id,
                verification=self._verification_result,
            )
            self._verification_result = None
            return

        self.result_repo.upsert_result(
            task_id=payload.task_id,
            final_price=payload.final_price,
            expected_sales=payload.expected_sales,
            expected_profit=payload.expected_profit,
            profit_growth=payload.profit_growth,
            is_pass=payload.is_pass,
            execute_strategy=execute_strategy,
            result_summary=payload.result_summary,
            review_required=review_required,
            execution_id=self.execution_id,
        )
        self.task_repo.set_suggested_range(task, payload.suggested_min_price, payload.suggested_max_price, execution_id=self.execution_id)
        self.task_repo.update_status(task, "MANUAL_REVIEW" if review_required else "COMPLETED", execution_id=self.execution_id)
