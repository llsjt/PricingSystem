from decimal import Decimal
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.agent_run_log import AgentRunLog
from app.utils.math_utils import money, ratio
from app.utils.json_utils import to_json_compatible


class LogRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_next_run_order(self, task_id: int) -> int:
        stmt = select(func.max(AgentRunLog.run_order)).where(AgentRunLog.task_id == task_id)
        value = self.db.scalar(stmt)
        return int(value or 0) + 1

    def append_log(
        self,
        task_id: int,
        agent_code: str,
        agent_name: str,
        run_status: str,
        input_summary: str,
        output_summary: str,
        output_payload: dict[str, Any] | None = None,
        suggested_price: Decimal | None = None,
        predicted_profit: Decimal | None = None,
        confidence_score: Decimal | float | None = None,
        risk_level: str | None = None,
        need_manual_review: bool = False,
        error_message: str | None = None,
    ) -> AgentRunLog:
        run_order = self.get_next_run_order(task_id)
        log = AgentRunLog(
            task_id=task_id,
            agent_code=agent_code,
            agent_name=agent_name,
            run_order=run_order,
            run_status=run_status,
            input_summary=input_summary,
            output_summary=output_summary,
            output_payload=to_json_compatible(output_payload),
            suggested_price=money(suggested_price) if suggested_price is not None else None,
            predicted_profit=money(predicted_profit) if predicted_profit is not None else None,
            confidence_score=ratio(confidence_score) if confidence_score is not None else None,
            risk_level=risk_level,
            need_manual_review=1 if need_manual_review else 0,
            error_message=error_message,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_by_task_id(self, task_id: int, limit: int = 200) -> list[AgentRunLog]:
        stmt = (
            select(AgentRunLog)
            .where(AgentRunLog.task_id == task_id)
            .order_by(desc(AgentRunLog.run_order), desc(AgentRunLog.id))
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
