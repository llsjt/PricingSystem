from sqlalchemy.orm import Session

from app.repos.result_repo import ResultRepo
from app.repos.task_repo import TaskRepo
from app.schemas.result import TaskFinalResult
from app.utils.text_utils import is_manual_review_action


class ResultWriterTool:
    def __init__(self, db: Session):
        self.result_repo = ResultRepo(db)
        self.task_repo = TaskRepo(db)

    def write_final_result(self, payload: TaskFinalResult) -> None:
        task = self.task_repo.get_by_id(payload.task_id)
        if task is None:
            raise ValueError(f"task not found: {payload.task_id}")
        if str(task.task_status or "").upper() == "CANCELLED":
            return

        review_required = (not payload.is_pass) or is_manual_review_action(payload.execute_strategy)

        self.result_repo.upsert_result(
            task_id=payload.task_id,
            final_price=payload.final_price,
            expected_sales=payload.expected_sales,
            expected_profit=payload.expected_profit,
            profit_growth=payload.profit_growth,
            is_pass=payload.is_pass,
            execute_strategy=payload.execute_strategy,
            result_summary=payload.result_summary,
            review_required=review_required,
        )
        self.task_repo.set_suggested_range(task, payload.suggested_min_price, payload.suggested_max_price)
        self.task_repo.update_status(task, "MANUAL_REVIEW" if review_required else "COMPLETED")
