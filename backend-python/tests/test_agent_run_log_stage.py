import json
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
from app.services import orchestration_service as orchestration_module
from app.services.orchestration_service import OrchestrationService
from app.tools.log_writer_tool import LogWriterTool


def _agent_validation_error_cls():
    return getattr(orchestration_module, "AgentOutputValidationError", RuntimeError)


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
                        run_attempt INT NOT NULL DEFAULT 0,
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


def _payload(task_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        task_id=task_id,
        strategy_goal="MAX_PROFIT",
        constraints={},
        product=SimpleNamespace(
            current_price=Decimal("29.90"),
            cost_price=Decimal("16.80"),
        ),
        metrics=[],
        traffic=[],
        baseline_sales=100,
        baseline_profit=Decimal("800.00"),
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
    )


def _valid_data_output() -> dict:
    return {
        "suggestedPrice": "29.90",
        "suggestedMinPrice": "27.90",
        "suggestedMaxPrice": "31.90",
        "expectedSales": 120,
        "expectedProfit": "980.00",
        "confidence": 0.82,
        "thinking": "data-thinking",
        "summary": "data-summary",
    }


def _valid_market_output() -> dict:
    return {
        "suggestedPrice": "30.50",
        "marketFloor": "26.50",
        "marketCeiling": "34.80",
        "marketMedian": "30.10",
        "marketAverage": "30.20",
        "confidence": 0.78,
        "thinking": "market-thinking",
        "summary": "market-summary",
        "competitorSamples": 5,
    }


def _valid_risk_output() -> dict:
    return {
        "isPass": False,
        "safeFloorPrice": "21.00",
        "suggestedPrice": "30.00",
        "riskLevel": "HIGH",
        "needManualReview": True,
        "thinking": "risk-thinking",
        "summary": "risk-summary",
    }


def _valid_manager_output() -> dict:
    return {
        "finalPrice": "30.00",
        "expectedSales": 118,
        "expectedProfit": "990.00",
        "profitGrowth": "190.00",
        "executeStrategy": "人工审核",
        "isPass": False,
        "thinking": "manager-thinking",
        "resultSummary": "manager-summary",
        "suggestedMinPrice": "28.00",
        "suggestedMaxPrice": "32.00",
    }


def _json_output(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


class _CallbackCrew:
    def __init__(self, callback, outputs: list[dict], final_output: dict):
        self.callback = callback
        self.outputs = outputs
        self.final_output = final_output

    def kickoff(self):
        for output in self.outputs:
            self.callback(SimpleNamespace(raw=_json_output(output)))
        return _json_output(self.final_output)


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
    assert completed.run_attempt == 0
    assert running.stage == "running"
    assert running.run_attempt == 0
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
        run_attempt=2,
    )

    assert failed.stage == "failed"
    assert failed.run_attempt == 2
    assert failed.display_order == 4
    assert failed.suggestion_json == {"error": True, "message": "LLM API timeout"}


def test_worker_failure_before_retry_clears_previous_running_and_failed_cards():
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=22)
    repo = LogRepo(db)
    repo.append_card(
        task_id=task.id,
        agent_name="数据分析Agent",
        display_order=1,
        thinking_summary="ok",
        evidence=[],
        suggestion={"summary": "ok"},
        run_attempt=0,
    )
    repo.append_running_card(
        task_id=task.id,
        agent_name="市场情报Agent",
        display_order=2,
        run_attempt=0,
    )
    repo.append_card(
        task_id=task.id,
        agent_name="市场情报Agent",
        display_order=2,
        thinking_summary="LLM 调用超时",
        evidence=[{"label": "错误摘要", "value": "LLM 调用超时"}],
        suggestion={"error": True, "message": "LLM 调用超时"},
        stage="failed",
        run_attempt=0,
    )

    req = SimpleNamespace(task_id=task.id, trace_id="trace-22")
    response = DispatchService(db).handle_worker_failure(req, "timeout", max_retries=2)
    logs = LogRepo(db).list_by_task_id(task.id)

    assert response.status == "RETRYING"
    assert [log.stage for log in logs] == ["completed"]
    assert logs[0].run_attempt == 0
    db.refresh(task)
    assert task.retry_count == 1


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


def test_orchestration_service_summarizes_agent_execution_timeout_separately():
    raw_error = RuntimeError(
        "Task '你正在为商品制定定价策略' execution timed out after 45 seconds. "
        "Consider increasing max_execution_time or optimizing the task."
    )

    summary = OrchestrationService._summarize_failure_message(raw_error)
    thinking, evidence, suggestion = OrchestrationService._build_failed_card(summary)

    assert summary == "Agent 执行超时"
    assert thinking == "Agent 执行超时"
    assert evidence == [{"label": "错误摘要", "value": "Agent 执行超时"}]
    assert suggestion == {"error": True, "message": "Agent 执行超时"}


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


def test_validate_agent_output_rejects_missing_required_data_price():
    invalid = _valid_data_output()
    invalid.pop("suggestedPrice")

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        OrchestrationService._validate_agent_output("DATA_ANALYSIS", invalid)

    assert "[DATA_ANALYSIS]" in str(exc_info.value)
    assert "输出结构校验失败" in str(exc_info.value)


def test_orchestration_validation_failure_writes_failed_card_and_blocks_result(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=5)
    invalid_data = _valid_data_output()
    invalid_data.pop("suggestedPrice")

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _CallbackCrew(kwargs["on_task_done"], [invalid_data], _valid_manager_output()),
    )

    service = OrchestrationService(db)
    result_calls = []
    service.result_tool = SimpleNamespace(write_final_result=result_calls.append)

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        service.run(_payload(task.id))

    logs = LogRepo(db).list_by_task_id(task.id)

    assert "[DATA_ANALYSIS]" in str(exc_info.value)
    assert result_calls == []
    assert [log.stage for log in logs] == ["running", "failed", "running"]
    assert logs[1].role_name == "数据分析Agent"
    assert logs[1].suggestion_json["error"] is True
    assert logs[1].suggestion_json["message"].startswith("[DATA_ANALYSIS]")


def test_validation_failure_keeps_task_outputs_aligned_for_manager(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=7)
    invalid_data = _valid_data_output()
    invalid_data.pop("suggestedPrice")
    captured_manager_context = []
    original_build_manager_card = OrchestrationService._build_manager_card

    def _capture_manager_context(parsed, data_parsed, market_parsed, risk_parsed):
        captured_manager_context.append((data_parsed, market_parsed, risk_parsed))
        return original_build_manager_card(parsed, data_parsed, market_parsed, risk_parsed)

    monkeypatch.setattr(
        OrchestrationService,
        "_build_manager_card",
        staticmethod(_capture_manager_context),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _CallbackCrew(
            kwargs["on_task_done"],
            [
                invalid_data,
                _valid_market_output(),
                _valid_risk_output(),
                _valid_manager_output(),
            ],
            _valid_manager_output(),
        ),
    )

    service = OrchestrationService(db)
    service.result_tool = SimpleNamespace(write_final_result=lambda payload: None)

    with pytest.raises(_agent_validation_error_cls()):
        service.run(_payload(task.id))

    assert captured_manager_context
    data_parsed, market_parsed, risk_parsed = captured_manager_context[0]
    assert data_parsed == {}
    assert market_parsed["suggestedPrice"] == Decimal("30.50")
    assert risk_parsed["suggestedPrice"] == Decimal("30.00")


def test_orchestration_final_manager_output_requires_final_price(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=6)
    final_output = _valid_manager_output()
    final_output.pop("finalPrice")

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _CallbackCrew(
            kwargs["on_task_done"],
            [
                _valid_data_output(),
                _valid_market_output(),
                _valid_risk_output(),
                _valid_manager_output(),
            ],
            final_output,
        ),
    )

    service = OrchestrationService(db)
    result_calls = []
    service.result_tool = SimpleNamespace(write_final_result=result_calls.append)

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        service.run(_payload(task.id))

    assert "[MANAGER_COORDINATOR]" in str(exc_info.value)
    assert result_calls == []


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
