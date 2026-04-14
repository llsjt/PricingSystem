from decimal import Decimal
from types import SimpleNamespace

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.db.base import Base
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_task import PricingTask
from app.repos.log_repo import LogRepo
from app.services.dispatch_service import DispatchService
from app.services.orchestration_service import OrchestrationService
from app.tools.log_writer_tool import LogWriterTool


def build_session(*tables) -> Session:
    engine = create_engine("sqlite:///:memory:")
    metadata_tables = [table for table in tables if table is not AgentRunLog.__table__]
    if metadata_tables:
        Base.metadata.create_all(engine, tables=metadata_tables)
    if AgentRunLog.__table__ in tables:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE agent_run_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id BIGINT NOT NULL,
                        role_name VARCHAR(50) NOT NULL,
                        speak_order INT NOT NULL,
                        thought_content TEXT DEFAULT NULL,
                        thinking_summary TEXT DEFAULT NULL,
                        evidence_json JSON DEFAULT NULL,
                        suggestion_json JSON DEFAULT NULL,
                        final_reason TEXT DEFAULT NULL,
                        display_order INT DEFAULT NULL,
                        stage VARCHAR(20) NOT NULL DEFAULT 'completed',
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_running_task(db: Session, task_id: int = 1) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=101,
        current_price=Decimal("19.90"),
        baseline_profit=Decimal("10.00"),
        task_status="RUNNING",
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_log_repo_writes_completed_and_running_stage():
    db = build_session(AgentRunLog.__table__)
    repo = LogRepo(db)

    completed = repo.append_card(
        task_id=1,
        agent_name="数据分析Agent",
        display_order=1,
        thinking_summary="已完成分析",
        evidence=[{"label": "x", "value": 1}],
        suggestion={"summary": "ok"},
    )
    running = repo.append_running_card(
        task_id=1,
        agent_name="市场情报Agent",
        display_order=2,
    )

    assert completed.stage == "completed"
    assert running.stage == "running"
    assert running.display_order == 2
    assert running.thinking_summary is None
    assert running.evidence_json == []
    assert running.suggestion_json == {}


def test_log_repo_writes_failed_stage_for_error_card():
    db = build_session(AgentRunLog.__table__)
    repo = LogRepo(db)

    failed = repo.append_card(
        task_id=1,
        agent_name="Manager Agent",
        display_order=4,
        thinking_summary="Agent execution failed: LLM API timeout",
        evidence=[{"label": "error", "value": "LLM API timeout"}],
        suggestion={"error": True, "message": "LLM API timeout"},
        stage="failed",
    )

    assert failed.stage == "failed"
    assert failed.display_order == 4
    assert failed.suggestion_json == {"error": True, "message": "LLM API timeout"}


def test_log_writer_skips_running_card_for_cancelled_task():
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=2)
    writer = LogWriterTool(db)

    writer.write_running_card(task_id=task.id, agent_name="数据分析Agent", display_order=1)
    task.task_status = "CANCELLED"
    db.commit()
    writer.write_running_card(task_id=task.id, agent_name="市场情报Agent", display_order=2)

    logs = LogRepo(db).list_by_task_id(task.id)
    assert [log.stage for log in logs] == ["running"]
    assert logs[0].role_name == "数据分析Agent"


def test_dispatch_logs_report_failed_run_status_for_legacy_error_card():
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=3)
    LogRepo(db).append_card(
        task_id=task.id,
        agent_name="Manager Agent",
        display_order=4,
        thinking_summary="Agent execution failed: LLM API timeout",
        evidence=[{"label": "error", "value": "LLM API timeout"}],
        suggestion={"error": True, "message": "LLM API timeout"},
    )

    response = DispatchService(db).get_logs(task.id)

    assert len(response.logs) == 1
    assert response.logs[0].stage == "failed"
    assert response.logs[0].run_status == "failed"


def test_orchestration_service_summarizes_timeout_failure_without_leaking_raw_details():
    raw_error = RuntimeError(
        "Task execution failed: LLM API timeout (connect=8s, read=30s, total=60s)"
    )

    summary = OrchestrationService._summarize_failure_message(raw_error)
    thinking, evidence, suggestion = OrchestrationService._build_failed_card(summary)

    assert summary == "LLM 调用超时"
    assert thinking == "LLM 调用超时"
    assert evidence == [{"label": "错误摘要", "value": "LLM 调用超时"}]
    assert suggestion == {"error": True, "message": "LLM 调用超时"}


def test_orchestration_service_falls_back_to_generic_failure_summary_for_prompt_like_errors():
    raw_error = RuntimeError(
        "Task `你正在为商品 [凉感阔腿裤高腰垂感款-260327135445704] 制定定价策略` failed"
    )

    summary = OrchestrationService._summarize_failure_message(raw_error)
    thinking, evidence, suggestion = OrchestrationService._build_failed_card(summary)

    assert summary == "CrewAI 任务执行失败"
    assert thinking == "CrewAI 任务执行失败"
    assert evidence == [{"label": "错误摘要", "value": "CrewAI 任务执行失败"}]
    assert suggestion == {"error": True, "message": "CrewAI 任务执行失败"}


def test_orchestration_service_writes_failed_stage_when_crew_kickoff_raises(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=4)

    class _FakeCrew:
        def kickoff(self):
            raise RuntimeError("Task `你正在为商品 [测试商品] 分析市场竞争态势` failed")

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _FakeCrew(),
    )

    payload = SimpleNamespace(
        task_id=task.id,
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
    )

    with pytest.raises(RuntimeError):
        OrchestrationService(db).run(payload)

    logs = LogRepo(db).list_by_task_id(task.id)

    assert [log.stage for log in logs] == ["running", "failed"]
    assert logs[-1].thinking_summary == "CrewAI 任务执行失败"
    assert logs[-1].suggestion_json == {"error": True, "message": "CrewAI 任务执行失败"}
