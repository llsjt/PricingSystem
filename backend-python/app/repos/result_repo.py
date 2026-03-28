from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pricing_result import PricingResult
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
    ) -> PricingResult:
        entity = self.get_by_task_id(task_id)
        if entity is None:
            entity = PricingResult(task_id=task_id, final_price=money(final_price), expected_profit=money(expected_profit))

        entity.final_price = money(final_price)
        entity.expected_sales = max(int(expected_sales or 0), 0)
        entity.expected_profit = money(expected_profit)
        entity.profit_growth = money(profit_growth)
        entity.is_pass = 1 if is_pass else 0
        entity.execute_strategy = execute_strategy
        entity.result_summary = result_summary

        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

