"""ResumeService contract tests for resume/retry behavior."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.crew.protocols import CrewRunPayload
from app.models.agent_run_log import AgentRunLog
from app.repos.log_repo import LogRepo
from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.services.resume_fingerprint import attach_resume_meta
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


def _payload(*, min_price: str = "90.00") -> CrewRunPayload:
    return CrewRunPayload(
        task_id=1,
        strategy_goal="PROFIT",
        constraints={
            "min_price": min_price,
            "max_price": "150.00",
            "max_discount_rate": "0.50",
            "force_manual_review": False,
        },
        product=ProductContext(
            productId=100,
            shopId=10,
            productName="测试商品",
            categoryName="日用",
            currentPrice="120.00",
            costPrice="70.00",
            stock=80,
        ),
        metrics=[
            DailyMetricSnapshot(
                statDate="2026-06-01",
                visitorCount=100,
                addCartCount=20,
                payBuyerCount=10,
                salesCount=10,
                turnover="1200.00",
                conversionRate="0.10",
            )
        ],
        traffic=[
            TrafficSnapshot(
                statDate="2026-06-01",
                trafficSource="search",
                impressionCount=1000,
                clickCount=100,
                visitorCount=90,
                payAmount="900.00",
                roi="2.00",
            )
        ],
        baseline_sales=100,
        baseline_profit="500.00",
        llm_api_key="secret",
        llm_base_url="https://llm.example.test",
        llm_model="model-a",
    )


def _insert_failed_row(
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
            thought_content="boom",
            thinking_summary="boom",
            evidence_json=[],
            suggestion_json={"error": True, "message": "boom"},
            raw_output_json=raw_output,
            display_order=order,
            stage="failed",
            run_attempt=run_attempt,
        )
    )
    db.commit()


def test_failed_raw_output_with_tool_audit_is_not_replayed():
    db = _build_session()
    _insert_failed_row(
        db,
        task_id=1,
        order=1,
        raw_output={"toolAudit": [{"toolName": "estimate_profit", "status": "error"}]},
    )

    plan = ResumeService(db).compute_resume_plan(task_id=1)

    assert plan.prior_outputs == {}
    assert plan.analysis_orders_to_run == [1, 2, 3]


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


def test_resume_plan_keeps_non_contiguous_reusable_outputs():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=3, raw={"agent": "risk"})

    plan = ResumeService(db).compute_resume_plan(task_id=1)

    assert plan.analysis_orders_to_run == [2]
    assert plan.prior_outputs == {
        1: {"agent": "data"},
        3: {"agent": "risk"},
    }


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


def test_resume_plan_reuses_output_when_payload_fingerprint_matches():
    db = _build_session()
    payload = _payload()
    _add_completed(
        db,
        task_id=1,
        order=1,
        raw=attach_resume_meta({"agent": "data"}, payload),
    )

    plan = ResumeService(db).compute_resume_plan(task_id=1, payload=payload)

    assert plan.prior_outputs == {1: {"agent": "data"}}
    assert plan.analysis_orders_to_run == [2, 3]


def test_resume_plan_does_not_reuse_output_when_payload_fingerprint_changes():
    db = _build_session()
    original_payload = _payload(min_price="90.00")
    changed_payload = _payload(min_price="95.00")
    _add_completed(
        db,
        task_id=1,
        order=1,
        raw=attach_resume_meta({"agent": "data"}, original_payload),
    )

    plan = ResumeService(db).compute_resume_plan(task_id=1, payload=changed_payload)

    assert plan.prior_outputs == {}
    assert plan.analysis_orders_to_run == [1, 2, 3]


def test_resume_plan_does_not_reuse_legacy_output_without_fingerprint_for_payload_run():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "legacy-data"})

    plan = ResumeService(db).compute_resume_plan(task_id=1, payload=_payload())

    assert plan.prior_outputs == {}
    assert plan.analysis_orders_to_run == [1, 2, 3]
