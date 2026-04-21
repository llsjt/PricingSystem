"""结果仓储模块，封装定价结果的查询与持久化操作。"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask
from app.utils.math_utils import money


class ResultRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_task_id(self, task_id: int) -> PricingResult | None:
        stmt = select(PricingResult).where(PricingResult.task_id == task_id).limit(1)
        return self.db.scalars(stmt).first()

    def upsert_result(
        self,
        task_id: int,
        final_price: Decimal,
        expected_sales: int,
        expected_profit: Decimal,
        profit_growth: Decimal,
        is_pass: bool,
        execute_strategy: str,
        result_summary: str,
        review_required: bool,
        execution_id: str | None = None,
    ) -> PricingResult:
        if execution_id and not self._can_write(task_id, execution_id):
            return PricingResult(task_id=task_id, execution_id=execution_id, final_price=money(final_price), expected_profit=money(expected_profit))
        entity = self.get_by_task_id(task_id)
        if entity is None:
            entity = PricingResult(task_id=task_id, execution_id=execution_id, final_price=money(final_price), expected_profit=money(expected_profit))

        entity.execution_id = execution_id
        entity.final_price = money(final_price)
        entity.expected_sales = max(int(expected_sales or 0), 0)
        entity.expected_profit = money(expected_profit)
        entity.profit_growth = money(profit_growth)
        entity.is_pass = 1 if is_pass else 0
        entity.execute_strategy = execute_strategy
        entity.result_summary = result_summary
        entity.review_required = 1 if review_required else 0

        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def _can_write(self, task_id: int, execution_id: str) -> bool:
        task = self.db.get(PricingTask, task_id)
        if task is None:
            return False
        status = str(task.task_status or "").upper()
        if status in {"COMPLETED", "FAILED", "CANCELLED", "MANUAL_REVIEW"}:
            return False
        return str(task.current_execution_id or "") == execution_id
