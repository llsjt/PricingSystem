"""ResumeService contract tests for resume/retry behavior."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.models.agent_run_log import AgentRunLog
from app.repos.log_repo import LogRepo
from app.services.resume_service import ResumeService


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE agent_run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id BIGINT NOT NULL,
                    execution_id VARCHAR(64) DEFAULT NULL,
                    role_name VARCHAR(50) NOT NULL,
                    speak_order INT NOT NULL,
                    thought_content TEXT DEFAULT NULL,
                    thinking_summary TEXT DEFAULT NULL,
                    evidence_json JSON DEFAULT NULL,
                    suggestion_json JSON DEFAULT NULL,
                    raw_output_json JSON DEFAULT NULL,
                    final_reason TEXT DEFAULT NULL,
                    display_order INT DEFAULT NULL,
                    stage VARCHAR(20) NOT NULL DEFAULT 'completed',
                    run_attempt INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def _add_completed(
    db: Session,
    task_id: int,
    order: int,
    raw: dict | None,
    run_attempt: int = 0,
) -> None:
    repo = LogRepo(db)
    repo.append_card(
        task_id=task_id,
        agent_name=f"Agent-{order}",
        display_order=order,
        thinking_summary="ok",
        evidence=[],
        suggestion={"summary": "ok"},
        run_attempt=run_attempt,
        raw_output=raw,
    )


def _insert_completed_row(
    db: Session,
    *,
    task_id: int,
    order: int,
    raw_output: dict | None,
    run_attempt: int = 0,
) -> None:
    db.add(
        AgentRunLog(
            task_id=task_id,
            role_name=f"Agent-{order}",
            speak_order=order,
            thought_content="ok",
            thinking_summary="ok",
            evidence_json=[],
            suggestion_json={"summary": "ok"},
            raw_output_json=raw_output,
            display_order=order,
            stage="completed",
            run_attempt=run_attempt,
        )
    )
    db.commit()


def _add_failed(db: Session, task_id: int, order: int, run_attempt: int = 0) -> None:
    repo = LogRepo(db)
    repo.append_card(
        task_id=task_id,
        agent_name=f"Agent-{order}",
        display_order=order,
        thinking_summary="boom",
        evidence=[],
        suggestion={"error": True, "message": "boom"},
        stage="failed",
        run_attempt=run_attempt,
    )


def test_empty_task_returns_full_run():
    db = _build_session()
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}


def test_data_done_resumes_from_market():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"suggestedPrice": "29.90"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior == {1: {"suggestedPrice": "29.90"}}


def test_data_and_market_done_resumes_from_risk():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=2, raw={"agent": "market"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 3
    assert prior == {1: {"agent": "data"}, 2: {"agent": "market"}}


def test_non_contiguous_prefix_breaks_at_first_gap():
    db = _build_session()
    _add_completed(db, task_id=1, order=2, raw={"agent": "market"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}


@pytest.mark.parametrize(
    ("raw_output", "case_label"),
    [
        (None, "null"),
        ({}, "empty-object"),
    ],
)
def test_completed_without_reusable_raw_output_treated_as_incomplete(raw_output: dict | None, case_label: str):
    db = _build_session()
    _insert_completed_row(db, task_id=1, order=1, raw_output=raw_output)
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}, case_label


def test_all_four_done_returns_past_last_order():
    db = _build_session()
    for order in (1, 2, 3, 4):
        _add_completed(db, task_id=1, order=order, raw={"order": order})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 5
    assert sorted(prior.keys()) == [1, 2, 3, 4]


def test_latest_run_attempt_wins_when_multiple_completed_rows_for_same_order():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"v": "old"}, run_attempt=0)
    _add_completed(db, task_id=1, order=1, raw={"v": "new"}, run_attempt=1)
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior[1] == {"v": "new"}


def test_failed_rows_do_not_count_as_completed():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"}, run_attempt=0)
    _add_failed(db, task_id=1, order=2, run_attempt=0)
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior == {1: {"agent": "data"}}


def test_different_tasks_are_isolated():
    db = _build_session()
    _add_completed(db, task_id=100, order=1, raw={"agent": "data-100"})
    _add_completed(db, task_id=200, order=1, raw={"agent": "data-200"})
    _add_completed(db, task_id=200, order=2, raw={"agent": "market-200"})

    svc = ResumeService(db)

    start_100, prior_100 = svc.compute_resume_point(task_id=100)
    start_200, prior_200 = svc.compute_resume_point(task_id=200)

    assert start_100 == 2
    assert prior_100 == {1: {"agent": "data-100"}}

    assert start_200 == 3
    assert prior_200 == {1: {"agent": "data-200"}, 2: {"agent": "market-200"}}


def test_resume_plan_only_replays_missing_analysis_orders():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=3, raw={"agent": "risk"})

    plan = ResumeService(db).compute_resume_plan(task_id=1)

    assert plan.analysis_orders_to_run == [2]
    assert plan.prior_outputs == {
        1: {"agent": "data"},
        3: {"agent": "risk"},
    }
    assert plan.manager_completed is False
    assert plan.should_run_manager_now is False
    assert plan.all_done is False


def test_resume_plan_keeps_non_contiguous_reusable_outputs_without_faking_continuous_prefix():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=3, raw={"agent": "risk"})

    service = ResumeService(db)
    plan = service.compute_resume_plan(task_id=1)
    start_from, prior = service.compute_resume_point(task_id=1)

    assert plan.analysis_orders_to_run == [2]
    assert plan.prior_outputs == {
        1: {"agent": "data"},
        3: {"agent": "risk"},
    }
    assert start_from == 2
    assert prior == {1: {"agent": "data"}}


def test_resume_plan_runs_only_manager_when_all_analysis_outputs_exist():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=2, raw={"agent": "market"})
    _add_completed(db, task_id=1, order=3, raw={"agent": "risk"})

    plan = ResumeService(db).compute_resume_plan(task_id=1)

    assert plan.analysis_orders_to_run == []
    assert plan.prior_outputs == {
        1: {"agent": "data"},
        2: {"agent": "market"},
        3: {"agent": "risk"},
    }
    assert plan.manager_completed is False
    assert plan.should_run_manager_now is True
    assert plan.all_done is False


def test_resume_plan_marks_all_done_when_manager_output_exists():
    db = _build_session()
    for order, agent in (
        (1, "data"),
        (2, "market"),
        (3, "risk"),
        (4, "manager"),
    ):
        _add_completed(db, task_id=1, order=order, raw={"agent": agent})

    plan = ResumeService(db).compute_resume_plan(task_id=1)

    assert plan.analysis_orders_to_run == []
    assert plan.manager_completed is True
    assert plan.should_run_manager_now is False
    assert plan.all_done is True
