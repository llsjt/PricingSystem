"""Atomic final result persistence with execution owner fencing."""

from app.domain.final_decision_verifier import (
    FinalDecisionVerifier,
    VerificationContext,
    VerificationResult,
    append_guardrail_summary,
)
from app.repos.result_repo import ResultRepo
from app.repos.task_repo import TaskRepo
from app.schemas.result import TaskFinalResult
from app.services.runtime_metrics import get_runtime_metrics
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY


class ExecutionOwnerChanged(RuntimeError):
    """Raised when finalization loses the current execution owner CAS."""


class ResultFinalizationService:
    def __init__(self, db, verifier: FinalDecisionVerifier | None = None):
        self.db = db
        self.task_repo = TaskRepo(db)
        self.result_repo = ResultRepo(db)
        self.verifier = verifier or FinalDecisionVerifier()

    def verify(self, context: VerificationContext) -> VerificationResult:
        return self.verifier.verify(context)

    def finalize_manual_review(
        self,
        final_result: TaskFinalResult,
        *,
        execution_id: str,
        verification: VerificationResult | None = None,
    ) -> TaskFinalResult:
        if not execution_id:
            raise ExecutionOwnerChanged("missing execution owner")

        checked_result = final_result
        if verification is not None:
            checked_result = final_result.model_copy(
                update={
                    "is_pass": bool(final_result.is_pass and verification.is_pass),
                    "execute_strategy": MANUAL_REVIEW_STRATEGY,
                    "result_summary": append_guardrail_summary(final_result.result_summary, verification),
                }
            )

        try:
            updated = self.task_repo.finalize_manual_review_if_owner(
                task_id=checked_result.task_id,
                execution_id=execution_id,
                suggested_min_price=checked_result.suggested_min_price,
                suggested_max_price=checked_result.suggested_max_price,
            )
            if updated != 1:
                self.db.rollback()
                get_runtime_metrics().increment("casConflictCount")
                raise ExecutionOwnerChanged("execution owner changed before finalization")

            self.result_repo.upsert_result_without_commit(
                task_id=checked_result.task_id,
                final_price=checked_result.final_price,
                expected_sales=checked_result.expected_sales,
                expected_profit=checked_result.expected_profit,
                profit_growth=checked_result.profit_growth,
                is_pass=checked_result.is_pass,
                execute_strategy=MANUAL_REVIEW_STRATEGY,
                result_summary=checked_result.result_summary,
                review_required=True,
                execution_id=execution_id,
            )
            self.db.commit()
            return checked_result
        except Exception:
            self.db.rollback()
            raise
