import json
from decimal import Decimal
from types import SimpleNamespace

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.crew.crew_factory import CrewBundle
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


def _opinion_id(task_id: int, agent_code: str, run_attempt: int = 0) -> str:
    return f"task:{task_id}:agent:{agent_code}:attempt:{run_attempt}"


def _attach_agent_opinion(task_id: int, payload: dict, agent_code: str, agent_name: str, *, kind: str, status: str) -> dict:
    enriched = dict(payload)
    enriched["agentOpinion"] = {
        "version": "v1",
        "opinionId": _opinion_id(task_id, agent_code),
        "taskId": task_id,
        "runAttempt": 0,
        "agentCode": agent_code,
        "agentName": agent_name,
        "kind": kind,
        "status": status,
        "summary": payload.get("summary") or payload.get("resultSummary") or f"{agent_name} summary",
        "confidence": payload.get("confidence", 0.72),
        "pricing": {
            "recommendedPrice": payload.get("suggestedPrice") or payload.get("finalPrice"),
            "minPrice": payload.get("suggestedMinPrice"),
            "maxPrice": payload.get("suggestedMaxPrice"),
            "safeFloorPrice": payload.get("safeFloorPrice"),
        },
        "impact": {
            "expectedSales": payload.get("expectedSales"),
            "expectedProfit": payload.get("expectedProfit"),
            "profitGrowth": payload.get("profitGrowth"),
        },
        "market": None,
        "risk": None,
        "evidence": [{"key": "summary", "label": "摘要", "value": payload.get("summary", "ok"), "source": "test"}],
        "rationale": {"thinking": payload.get("thinking", "thinking"), "assumptions": [], "notes": []},
        "relations": {
            "dependsOnOpinionIds": [],
            "acceptedOpinionIds": [],
            "rejectedOpinionIds": [],
            "conflictOpinionIds": [],
            "selectedOpinionIds": [],
        },
        "decision": None,
    }
    return enriched


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
        "consensusScore": 0.72,
        "conflicts": [
            {
                "topic": "建议价差异",
                "dataOpinion": "数据 Agent 建议 31.00",
                "marketOpinion": "市场 Agent 建议 29.50",
                "riskOpinion": "风控 Agent 要求不低于 28.00",
                "decision": "采用 30.00 的保守折中价",
            }
        ],
        "acceptedOpinions": [
            "采纳风控安全底价",
            "采纳市场样本不足时保守处理",
        ],
        "rejectedOpinions": [
            "未完全采纳数据 Agent 的激进提价建议",
        ],
        "arbitrationSummary": "先满足风控底线，再结合市场样本质量保守定价",
    }


def _json_output(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


class _FakeTaskOutput:
    """Mock for CrewAI TaskOutput — 只提供 .raw 字段供 orchestration 读取。"""

    def __init__(self, raw: str):
        self.raw = raw


class _FakeTask:
    """Mock Task 对象：execute_sync 直接返回预设的 JSON 原始字符串。"""

    def __init__(self, raw_json: str):
        self._raw_json = raw_json
        self.captured_context: str | None = None

    def execute_sync(self, agent=None, context=None, tools=None):
        self.captured_context = context
        return _FakeTaskOutput(self._raw_json)


class _RaisingTask:
    """Mock Task 对象：execute_sync 抛出预设异常，用于模拟单 Agent 执行失败。"""

    def __init__(self, error: BaseException):
        self._error = error

    def execute_sync(self, agent=None, context=None, tools=None):
        raise self._error


def _fake_bundle(outputs: list) -> CrewBundle:
    """为 4 个 Agent 构造伪 CrewBundle。

    outputs: 长度 <= 4 的列表；每个元素可以是 dict(成功输出)、str(原始 JSON) 或 Exception(失败)。
    不足 4 个时后续任务以空 dict 兜底（不会被执行则不触发）。
    """
    tasks: list = []
    for item in outputs:
        if isinstance(item, BaseException):
            tasks.append(_RaisingTask(item))
        elif isinstance(item, str):
            tasks.append(_FakeTask(item))
        else:
            tasks.append(_FakeTask(_json_output(item)))
    # 补齐 4 个 Task（未被执行时不触发，仅满足下标访问）
    while len(tasks) < 4:
        tasks.append(_FakeTask("{}"))

    fake_agent = SimpleNamespace(tools=[])
    return CrewBundle(
        crew=None,  # type: ignore[arg-type]  # 新流程不再调用 Crew.kickoff
        tasks=tasks,  # type: ignore[arg-type]
        agents_by_order={1: fake_agent, 2: fake_agent, 3: fake_agent, 4: fake_agent},  # type: ignore[arg-type]
    )


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
    completed_orders = sorted(log.display_order for log in logs if log.stage == "completed")
    failed_orders = sorted(log.display_order for log in logs if log.stage == "failed")
    running_orders = sorted(log.display_order for log in logs if log.stage == "running")

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


@pytest.mark.parametrize("opinion_key", ["agentOpinion", "agent_opinion"])
def test_parse_and_normalize_output_recovers_from_invalid_llm_agent_opinion(opinion_key: str):
    service = OrchestrationService(build_session())
    raw_output = _valid_data_output()
    raw_output[opinion_key] = {
        "version": "1.0",
        "opinionId": "task:demo:agent:bad",
        "taskId": "TASK-PRICING-001",
        "runAttempt": 0,
        "agentCode": "AGENT-001",
        "agentName": "数据分析Agent",
        "kind": "pricing_strategy",
        "status": "completed",
        "summary": "bad opinion from llm",
        "confidence": 0.9,
        "pricing": {"recommendedPrice": "29.90"},
        "impact": "利润增加，销量小幅下降",
        "evidence": ["工具计算销量1090", "利润41027.6"],
        "rationale": "利润优先策略下，收益高于销量损失范围内",
        "relations": ["成本价43.14", "基线销量1137"],
    }

    parsed = service._parse_and_validate_output(order=1, raw=_json_output(raw_output))

    assert "agentOpinion" not in parsed
    assert "agent_opinion" not in parsed

    normalized = service._normalize_output_with_agent_opinion(
        payload=_payload(task_id=54),
        order=1,
        parsed=parsed,
        prior_outputs={},
    )

    assert normalized["agentOpinion"]["version"] == "v1"
    assert normalized["agentOpinion"]["taskId"] == 54
    assert normalized["agentOpinion"]["agentCode"] == "DATA_ANALYSIS"
    assert normalized["agentOpinion"]["opinionId"] == _opinion_id(54, "DATA_ANALYSIS")


def test_build_manager_card_exposes_arbitration_fields():
    thinking, evidence, suggestion, reason_why = OrchestrationService._build_manager_card(
        _valid_manager_output(),
        _valid_data_output(),
        _valid_market_output(),
        _valid_risk_output(),
    )

    assert thinking == "manager-thinking"
    assert len(evidence) == 4
    assert suggestion["finalPrice"] == 30.0
    assert suggestion["consensusScore"] == 0.72
    assert suggestion["disagreementPoints"][0]["topic"]
    assert suggestion["acceptedOpinions"] == [
        "采纳风控安全底价",
        "采纳市场样本不足时保守处理",
    ]
    assert suggestion["rejectedOpinions"] == [
        "未完全采纳数据 Agent 的激进提价建议",
    ]
    assert suggestion["arbitrationDecision"] == _valid_manager_output()["arbitrationSummary"]
    assert "conflicts" not in suggestion
    assert "arbitrationSummary" not in suggestion
    assert reason_why == "manager-summary"


def test_build_manager_card_preserves_zero_consensus_score():
    manager_output = _valid_manager_output()
    manager_output["consensusScore"] = 0

    _thinking, _evidence, suggestion, _reason_why = OrchestrationService._build_manager_card(
        manager_output,
        _valid_data_output(),
        _valid_market_output(),
        _valid_risk_output(),
    )

    assert suggestion["consensusScore"] == 0.0


def test_build_manager_card_reads_legacy_manager_aliases_but_writes_only_normalized_fields():
    manager_output = {
        **_valid_manager_output(),
        "decisionReason": "legacy reason",
        "selectedOption": "MARKET_INTEL",
    }
    manager_output.pop("acceptedOpinions", None)
    manager_output.pop("rejectedOpinions", None)

    _thinking, _evidence, suggestion, reason_why = OrchestrationService._build_manager_card(
        manager_output,
        _valid_data_output(),
        _valid_market_output(),
        _valid_risk_output(),
    )

    assert suggestion["arbitrationDecision"] == manager_output["arbitrationSummary"]
    assert suggestion["arbitrationReason"] == "legacy reason"
    assert suggestion["selectedAgent"] == "MARKET_INTEL"
    assert "decisionReason" not in suggestion
    assert "selectedOption" not in suggestion
    assert reason_why == "manager-summary"


def test_write_agent_success_card_backfills_agent_opinion_into_raw_output():
    db = build_session(AgentRunLog.__table__)
    payload = _payload(task_id=51)
    service = OrchestrationService(db)

    service._write_agent_success_card(
        payload=payload,
        order=1,
        parsed=_valid_data_output(),
        prior_outputs={},
    )

    log = LogRepo(db).list_by_task_id(payload.task_id)[0]
    raw_output = log.raw_output_json

    assert raw_output is not None
    assert raw_output["agentOpinion"]["opinionId"] == _opinion_id(payload.task_id, "DATA_ANALYSIS")
    assert raw_output["agentOpinion"]["pricing"]["recommendedPrice"] == "29.90"
    assert "agentOpinion" not in log.suggestion_json


def test_write_agent_success_card_uses_current_retry_count_for_opinion_run_attempt():
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=510)
    task.retry_count = 2
    db.commit()
    payload = _payload(task_id=task.id)
    service = OrchestrationService(db)

    service._write_agent_success_card(
        payload=payload,
        order=1,
        parsed=_valid_data_output(),
        prior_outputs={},
    )

    log = LogRepo(db).list_by_task_id(task.id)[0]
    assert log.run_attempt == 2
    assert log.raw_output_json["agentOpinion"]["runAttempt"] == 2
    assert log.raw_output_json["agentOpinion"]["opinionId"] == _opinion_id(task.id, "DATA_ANALYSIS", 2)


def test_format_opinions_for_manager_context_prefers_agent_opinion_and_backfills_legacy():
    task_id = 52
    prior_outputs = {
        1: _valid_data_output(),
        2: _attach_agent_opinion(
            task_id,
            _valid_market_output(),
            "MARKET_INTEL",
            "市场情报Agent",
            kind="MARKET_ASSESSMENT",
            status="PROPOSED",
        ),
        3: _valid_risk_output(),
    }

    context = OrchestrationService._format_opinions_for_manager_context(prior_outputs)

    assert context is not None
    assert "[AgentOpinion 列表]" in context
    assert _opinion_id(task_id, "DATA_ANALYSIS") in context
    assert _opinion_id(task_id, "MARKET_INTEL") in context
    assert _opinion_id(task_id, "RISK_CONTROL") in context
    assert "历史输出 JSON" not in context


def test_manager_agent_invalid_opinion_reference_raises_validation_error(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=53)

    bad_manager = _attach_agent_opinion(
        task.id,
        _valid_manager_output(),
        "MANAGER_COORDINATOR",
        "缁忕悊鍗忚皟Agent",
        kind="ARBITRATION",
        status="MERGED",
    )
    bad_manager["agentOpinion"]["relations"]["dependsOnOpinionIds"] = [
        _opinion_id(task.id, "DATA_ANALYSIS"),
        _opinion_id(task.id, "MARKET_INTEL"),
        _opinion_id(task.id, "RISK_CONTROL"),
    ]
    bad_manager["agentOpinion"]["relations"]["acceptedOpinionIds"] = ["task:999:agent:UNKNOWN:attempt:0"]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle(
            [
                _valid_data_output(),
                _valid_market_output(),
                _valid_risk_output(),
                bad_manager,
            ]
        ),
    )

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        OrchestrationService(db).run(_payload(task.id))

    assert "acceptedOpinionIds" in str(exc_info.value)


def test_orchestration_service_reruns_only_manager_after_manager_failure(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=54)
    task.retry_count = 1
    db.commit()
    repo = LogRepo(db)
    repo.append_card(
        task_id=task.id,
        agent_name="閺佺増宓侀崚鍡樼€紸gent",
        display_order=1,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_data_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="鐢倸婧€閹懏濮gent",
        display_order=2,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_market_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="妞嬪酣娅撻幒褍鍩桝gent",
        display_order=3,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_risk_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="缂佸繒鎮婇崡蹇氱殶Agent",
        display_order=4,
        thinking_summary="boom",
        evidence=[],
        suggestion={"error": True, "message": "boom"},
        stage="failed",
    )

    bundle = _fake_bundle(
        [
            _valid_data_output(),
            _valid_market_output(),
            _valid_risk_output(),
            _valid_manager_output(),
        ]
    )
    bundle.tasks[0].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("data task should not rerun"))  # type: ignore[assignment]
    bundle.tasks[1].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("market task should not rerun"))  # type: ignore[assignment]
    bundle.tasks[2].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("risk task should not rerun"))  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: bundle,
    )

    service = OrchestrationService(db)
    service.result_tool = SimpleNamespace(write_final_result=lambda payload: None)
    service.run(_payload(task.id))

    manager_context = bundle.tasks[3].captured_context
    assert manager_context is not None
    assert _opinion_id(task.id, "DATA_ANALYSIS", 1) in manager_context
    assert _opinion_id(task.id, "MARKET_INTEL", 1) in manager_context
    assert _opinion_id(task.id, "RISK_CONTROL", 1) in manager_context

    logs = LogRepo(db).list_by_task_id(task.id)
    completed_orders = [log.display_order for log in logs if log.stage == "completed"]
    current_attempt_completed = sorted(
        log.display_order for log in logs if log.stage == "completed" and log.run_attempt == 1
    )
    current_attempt_analysis_logs = [
        (log.display_order, log.stage)
        for log in logs
        if log.run_attempt == 1 and log.display_order in {1, 2, 3}
    ]
    assert completed_orders.count(1) == 1
    assert completed_orders.count(2) == 1
    assert completed_orders.count(3) == 1
    assert completed_orders.count(4) == 1
    assert current_attempt_completed == [4]
    assert current_attempt_analysis_logs == []


def test_orchestration_service_runs_only_manager_without_writing_replay_completed_cards(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=55)
    task.retry_count = 1
    db.commit()
    repo = LogRepo(db)
    for order, raw_output in (
        (1, _valid_data_output()),
        (2, _valid_market_output()),
        (3, _valid_risk_output()),
    ):
        repo.append_card(
            task_id=task.id,
            agent_name=f"Agent-{order}",
            display_order=order,
            thinking_summary="done",
            evidence=[],
            suggestion={"summary": "done"},
            raw_output=raw_output,
            run_attempt=0,
        )

    bundle = _fake_bundle(
        [
            _valid_data_output(),
            _valid_market_output(),
            _valid_risk_output(),
            _valid_manager_output(),
        ]
    )
    bundle.tasks[0].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("data task should not rerun"))  # type: ignore[assignment]
    bundle.tasks[1].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("market task should not rerun"))  # type: ignore[assignment]
    bundle.tasks[2].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("risk task should not rerun"))  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: bundle,
    )

    service = OrchestrationService(db)
    service.result_tool = SimpleNamespace(write_final_result=lambda payload: None)
    service.run(_payload(task.id))

    manager_context = bundle.tasks[3].captured_context
    assert manager_context is not None
    assert _opinion_id(task.id, "DATA_ANALYSIS", 1) in manager_context
    assert _opinion_id(task.id, "MARKET_INTEL", 1) in manager_context
    assert _opinion_id(task.id, "RISK_CONTROL", 1) in manager_context

    logs = LogRepo(db).list_by_task_id(task.id)
    current_attempt_completed = sorted(
        log.display_order for log in logs if log.stage == "completed" and log.run_attempt == 1
    )
    current_attempt_analysis_logs = [
        (log.display_order, log.stage)
        for log in logs
        if log.run_attempt == 1 and log.display_order in {1, 2, 3}
    ]
    assert current_attempt_completed == [4]
    assert current_attempt_analysis_logs == []


def test_orchestration_validation_failure_writes_failed_card_and_blocks_result(monkeypatch):
    """数据分析 Agent 输出校验失败时，并行同轮已完成的分析卡片应保留，Manager 不启动。"""
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
        lambda **kwargs: _fake_bundle([invalid_data, _valid_market_output(), _valid_risk_output()]),
    )

    service = OrchestrationService(db)
    result_calls = []
    service.result_tool = SimpleNamespace(write_final_result=result_calls.append)

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        service.run(_payload(task.id))

    logs = LogRepo(db).list_by_task_id(task.id)
    completed_orders = sorted(log.display_order for log in logs if log.stage == "completed")
    failed_orders = sorted(log.display_order for log in logs if log.stage == "failed")
    running_orders = sorted(log.display_order for log in logs if log.stage == "running")

    assert "[DATA_ANALYSIS]" in str(exc_info.value)
    assert result_calls == []
    assert running_orders == [1, 2, 3]
    assert completed_orders == [2, 3]
    assert failed_orders == [1]
    assert 4 not in [log.display_order for log in logs]
    failed_card = next(log for log in logs if log.display_order == 1 and log.stage == "failed")
    assert failed_card.suggestion_json["error"] is True
    assert failed_card.suggestion_json["message"].startswith("[DATA_ANALYSIS]")

def test_validation_failure_aborts_immediately_skipping_downstream_agents(monkeypatch):
    """分析层校验失败时，Manager 不执行，但其它独立分析 Agent 可以完成。"""
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=7)

    invalid_data = _valid_data_output()
    invalid_data.pop("suggestedPrice")

    bundle = _fake_bundle([invalid_data, _valid_market_output(), _valid_risk_output(), _valid_manager_output()])
    bundle.tasks[3].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("manager should not run after analysis validation failure"))  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: bundle,
    )

    service = OrchestrationService(db)
    result_calls: list = []
    service.result_tool = SimpleNamespace(write_final_result=result_calls.append)

    with pytest.raises(_agent_validation_error_cls()):
        service.run(_payload(task.id))

    assert result_calls == []
    logs = LogRepo(db).list_by_task_id(task.id)
    completed_orders = sorted(log.display_order for log in logs if log.stage == "completed")
    failed_orders = sorted(log.display_order for log in logs if log.stage == "failed")
    assert completed_orders == [2, 3]
    assert failed_orders == [1]
    assert 4 not in [log.display_order for log in logs]

def test_orchestration_service_writes_three_analysis_running_cards_before_collecting_results(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=31)

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle(
            [
                _valid_data_output(),
                _valid_market_output(),
                _valid_risk_output(),
                _valid_manager_output(),
            ]
        ),
    )

    service = OrchestrationService(db)
    service.result_tool = SimpleNamespace(write_final_result=lambda payload: None)
    service.run(_payload(task.id))

    ordered_logs = db.query(AgentRunLog).order_by(AgentRunLog.id.asc()).all()
    assert [(log.display_order, log.stage) for log in ordered_logs[:3]] == [
        (1, "running"),
        (2, "running"),
        (3, "running"),
    ]

def test_orchestration_service_only_replays_missing_analysis_agents_before_running_manager(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=32)
    task.retry_count = 1
    db.commit()
    repo = LogRepo(db)
    repo.append_card(
        task_id=task.id,
        agent_name="鏁版嵁鍒嗘瀽Agent",
        display_order=1,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_data_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="椋庨櫓鎺у埗Agent",
        display_order=3,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_risk_output(),
    )

    bundle = _fake_bundle(
        [
            _valid_data_output(),
            _valid_market_output(),
            _valid_risk_output(),
            _valid_manager_output(),
        ]
    )
    bundle.tasks[0].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("data task should not rerun"))  # type: ignore[assignment]
    bundle.tasks[2].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("risk task should not rerun"))  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: bundle,
    )

    service = OrchestrationService(db)
    service.result_tool = SimpleNamespace(write_final_result=lambda payload: None)
    service.run(_payload(task.id))

    manager_context = bundle.tasks[3].captured_context
    assert manager_context is not None
    assert "[AgentOpinion 列表]" in manager_context
    assert _opinion_id(task.id, "DATA_ANALYSIS", 1) in manager_context
    assert _opinion_id(task.id, "MARKET_INTEL", 1) in manager_context
    assert _opinion_id(task.id, "RISK_CONTROL", 1) in manager_context
    assert '"suggestedPrice": "30.50"' not in manager_context

    logs = LogRepo(db).list_by_task_id(task.id)
    current_attempt_completed = sorted(
        log.display_order for log in logs if log.stage == "completed" and log.run_attempt == 1
    )
    current_attempt_replayed_analysis = [
        (log.display_order, log.stage)
        for log in logs
        if log.run_attempt == 1 and log.display_order in {1, 3}
    ]
    assert current_attempt_completed == [2, 4]
    assert current_attempt_replayed_analysis == []


def test_parallel_analysis_failure_keeps_other_completed_cards_and_blocks_manager(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=33)

    bundle = _fake_bundle(
        [
            _valid_data_output(),
            RuntimeError("market failed"),
            _valid_risk_output(),
            _valid_manager_output(),
        ]
    )
    bundle.tasks[3].execute_sync = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("manager should not run when analysis agent fails"))  # type: ignore[assignment]

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: bundle,
    )

    with pytest.raises(RuntimeError):
        OrchestrationService(db).run(_payload(task.id))

    logs = LogRepo(db).list_by_task_id(task.id)
    completed_orders = sorted(log.display_order for log in logs if log.stage == "completed")
    failed_orders = sorted(log.display_order for log in logs if log.stage == "failed")

    assert completed_orders == [1, 3]
    assert failed_orders == [2]
    assert 4 not in [log.display_order for log in logs]


def test_orchestration_final_manager_output_requires_final_price(monkeypatch):
    """经理 Agent 输出缺 finalPrice → 应直接报错并阻止 pricing_result 写入。"""
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=6)
    invalid_manager = _valid_manager_output()
    invalid_manager.pop("finalPrice")

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle(
            [
                _valid_data_output(),
                _valid_market_output(),
                _valid_risk_output(),
                invalid_manager,
            ]
        ),
    )

    service = OrchestrationService(db)
    result_calls = []
    service.result_tool = SimpleNamespace(write_final_result=result_calls.append)

    with pytest.raises(_agent_validation_error_cls()) as exc_info:
        service.run(_payload(task.id))

    assert "[MANAGER_COORDINATOR]" in str(exc_info.value)
    assert result_calls == []


def test_orchestration_service_writes_failed_stage_when_task_execute_sync_raises(monkeypatch):
    """单个分析 Agent 执行异常时，其他并行分析结果保留且 Manager 不执行。"""
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=4)

    raised = RuntimeError("Task `你正在为商品 [测试商品] 分析市场竞争态势` failed")

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle([raised, _valid_market_output(), _valid_risk_output(), _valid_manager_output()]),
    )

    with pytest.raises(RuntimeError):
        OrchestrationService(db).run(_payload(task.id))

    logs = LogRepo(db).list_by_task_id(task.id)
    completed_orders = sorted(log.display_order for log in logs if log.stage == "completed")
    failed_orders = sorted(log.display_order for log in logs if log.stage == "failed")
    assert completed_orders == [2, 3]
    assert failed_orders == [1]
    failed_card = next(log for log in logs if log.display_order == 1 and log.stage == "failed")
    assert failed_card.thinking_summary == "CrewAI 任务执行失败"
    assert failed_card.suggestion_json == {"error": True, "message": "CrewAI 任务执行失败"}
def test_orchestration_service_replays_legacy_manager_output_without_arbitration_fields(monkeypatch):
    db = build_session(PricingTask.__table__, AgentRunLog.__table__)
    task = create_running_task(db, task_id=41)
    repo = LogRepo(db)
    repo.append_card(
        task_id=task.id,
        agent_name="鏁版嵁鍒嗘瀽Agent",
        display_order=1,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_data_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="甯傚満鎯呮姤Agent",
        display_order=2,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_market_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="椋庨櫓鎺у埗Agent",
        display_order=3,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output=_valid_risk_output(),
    )
    repo.append_card(
        task_id=task.id,
        agent_name="缁忕悊鍗忚皟Agent",
        display_order=4,
        thinking_summary="done",
        evidence=[],
        suggestion={"summary": "done"},
        raw_output={
            "finalPrice": "30.00",
            "expectedSales": 118,
            "expectedProfit": "990.00",
            "profitGrowth": "190.00",
            "executeStrategy": orchestration_module.MANUAL_REVIEW_STRATEGY,
            "isPass": False,
            "thinking": "manager-thinking",
            "resultSummary": "manager-summary",
            "suggestedMinPrice": "28.00",
            "suggestedMaxPrice": "32.00",
        },
    )

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle(
            [
                _valid_data_output(),
                _valid_market_output(),
                _valid_risk_output(),
                _valid_manager_output(),
            ]
        ),
    )

    service = OrchestrationService(db)
    captured_results: list = []
    service.result_tool = SimpleNamespace(write_final_result=captured_results.append)

    result = service.run(_payload(task.id))

    assert result.final_price == Decimal("30.00")
    assert result.result_summary == "manager-summary"
    assert len(captured_results) == 1
