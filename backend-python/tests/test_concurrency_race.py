from backend_python_tests_support import build_result_session, create_pricing_task, final_result

from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask
from app.repos.task_repo import TaskRepo
from app.services.result_finalization_service import ExecutionOwnerChanged, ResultFinalizationService


def test_finalize_loses_cas_when_cancel_wins():
    db = build_result_session()
    create_pricing_task(db, task_id=101, status="RUNNING", execution_id="exec-current")

    task = db.get(PricingTask, 101)
    TaskRepo(db).mark_cancelled(task, failure_reason="user cancelled")

    try:
        ResultFinalizationService(db).finalize_manual_review(final_result(101), execution_id="exec-current")
        raise AssertionError("expected ExecutionOwnerChanged")
    except ExecutionOwnerChanged:
        pass

    refreshed = db.get(PricingTask, 101)
    assert refreshed.task_status == "CANCELLED"
    assert db.query(PricingResult).count() == 0


def test_cancel_loses_when_finalize_wins():
    db = build_result_session()
    create_pricing_task(db, task_id=102, status="RUNNING", execution_id="exec-current")

    ResultFinalizationService(db).finalize_manual_review(final_result(102), execution_id="exec-current")
    task = db.get(PricingTask, 102)
    TaskRepo(db).mark_cancelled(task, failure_reason="late cancel")

    refreshed = db.get(PricingTask, 102)
    assert refreshed.task_status == "MANUAL_REVIEW"
    assert db.query(PricingResult).filter(PricingResult.task_id == 102).count() == 1
