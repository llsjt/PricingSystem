from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.repos.log_repo import LogRepo


class LogWriterTool:
    def __init__(self, db: Session):
        self.log_repo = LogRepo(db)

    def write(
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
    ) -> None:
        self.log_repo.append_log(
            task_id=task_id,
            agent_code=agent_code,
            agent_name=agent_name,
            run_status=run_status,
            input_summary=input_summary,
            output_summary=output_summary,
            output_payload=output_payload,
            suggested_price=suggested_price,
            predicted_profit=predicted_profit,
            confidence_score=confidence_score,
            risk_level=risk_level,
            need_manual_review=need_manual_review,
            error_message=error_message,
        )

