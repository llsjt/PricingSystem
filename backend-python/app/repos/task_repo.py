from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pricing_task import PricingTask
from app.utils.math_utils import money


class TaskRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, task_id: int) -> PricingTask | None:
        return self.db.get(PricingTask, task_id)

    def update_status(self, task: PricingTask, status: str) -> PricingTask:
        task.task_status = status
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def set_suggested_range(self, task: PricingTask, min_price: Decimal, max_price: Decimal) -> PricingTask:
        task.suggested_min_price = money(min_price)
        task.suggested_max_price = money(max_price)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def find_by_code(self, task_code: str) -> PricingTask | None:
        stmt = select(PricingTask).where(PricingTask.task_code == task_code).limit(1)
        return self.db.scalars(stmt).first()

