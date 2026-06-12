import json
from dataclasses import dataclass
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.crew.crew_factory import CrewBundle
from app.db.base import Base
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_task import PricingTask
from app.repos.log_repo import LogRepo
from app.services.orchestration_service import OrchestrationService
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__])
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


def _create_task(db: Session, task_id: int) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=101,
        current_price=Decimal("120.00"),
        baseline_profit=Decimal("500.00"),
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
        constraints={
            "min_profit_rate": 0.2,
            "max_discount_rate": 0.5,
            "min_price": 90,
            "max_price": 150,
            "force_manual_review": False,
        },
        product=SimpleNamespace(
            current_price=Decimal("120.00"),
            cost_price=Decimal("80.00"),
        ),
        metrics=[],
        traffic=[],
        baseline_sales=100,
        baseline_profit=Decimal("500.00"),
        llm_api_key=None,
        llm_base_url=None,
        llm_model=None,
    )


def _data_output() -> dict[str, Any]:
    return {
        "suggestedPrice": "110.00",
        "suggestedMinPrice": "100.00",
        "suggestedMaxPrice": "120.00",
        "expectedSales": 100,
        "expectedProfit": "2500.00",
        "confidence": 0.8,
        "thinking": "data-thinking",
        "summary": "data-summary",
    }


def _market_output() -> dict[str, Any]:
    return {
        "suggestedPrice": "110.20",
        "marketFloor": "100.00",
        "marketCeiling": "140.00",
        "marketMedian": "111.00",
        "marketAverage": "112.00",
        "confidence": 0.8,
        "thinking": "market-thinking",
        "summary": "market-summary",
        "validCompetitorCount": 5,
        "sourceStatus": "OK",
        "dataQuality": "HIGH",
    }


def _risk_output() -> dict[str, Any]:
    return {
        "isPass": True,
        "safeFloorPrice": "100.00",
        "suggestedPrice": "110.00",
        "riskLevel": "LOW",
        "needManualReview": False,
        "thinking": "risk-thinking",
        "summary": "risk-summary",
    }


def _manager_output(
    *,
    decision: str,
    summary_prefix: str,
    selected_agent: str | None = "DATA_ANALYSIS",
    selected_price: str | None = "110.00",
) -> dict[str, Any]:
    return {
        "finalPrice": "110.00",
        "expectedSales": 100,
        "expectedProfit": "2500.00",
        "profitGrowth": "2000.00",
        "executeStrategy": MANUAL_REVIEW_STRATEGY,
        "isPass": True,
        "thinking": "manager-thinking",
        "resultSummary": f"{summary_prefix}：按利润优先处理，建议人工确认下一步动作。",
        "suggestedMinPrice": "100.00",
        "suggestedMaxPrice": "120.00",
        "consensusScore": 0.8,
        "disagreementSummary": "none",
        "disagreementPoints": [],
        "acceptedOpinions": ["data"],
        "rejectedOpinions": [],
        "arbitrationDecision": decision,
        "arbitrationReason": f"{decision} reason",
        "selectedAgent": selected_agent,
        "selectedPrice": selected_price,
        "selectedStrategy": MANUAL_REVIEW_STRATEGY,
    }


class _FakeTaskOutput:
    def __init__(self, raw: str):
        self.raw = raw


class _FakeTask:
    def __init__(self, raw_payload: dict[str, Any], audit: list[dict[str, Any]] | None = None):
        self.raw = json.dumps(raw_payload, ensure_ascii=False)
        self.audit = audit or []

    def execute_sync(self, agent=None, context=None, tools=None):  # noqa: ANN001, ARG002
        from app.tools.tool_context import active_tool_context

        ctx = active_tool_context.get()
        if ctx is not None:
            ctx.tool_audit_logs.extend(self.audit)
        return _FakeTaskOutput(self.raw)


@dataclass(frozen=True)
class _Scenario:
    name: str
    decision: str
    summary_prefix: str
    audit: list[dict[str, Any]]
    selected_agent: str | None = "DATA_ANALYSIS"
    selected_price: str | None = "110.00"


def _fake_bundle(scenario: _Scenario) -> CrewBundle:
    fake_agent = SimpleNamespace(tools=[])
    return CrewBundle(
        crew=None,  # type: ignore[arg-type]
        tasks=[
            _FakeTask(_data_output()),
            _FakeTask(_market_output()),
            _FakeTask(_risk_output()),
            _FakeTask(
                _manager_output(
                    decision=scenario.decision,
                    summary_prefix=scenario.summary_prefix,
                    selected_agent=scenario.selected_agent,
                    selected_price=scenario.selected_price,
                ),
                audit=scenario.audit,
            ),
        ],  # type: ignore[arg-type]
        agents_by_order={1: fake_agent, 2: fake_agent, 3: fake_agent, 4: fake_agent},  # type: ignore[arg-type]
    )


SCENARIOS = [
    _Scenario("fast_path", "FAST_PATH", "可确认", []),
    _Scenario(
        "profit_verification",
        "PROFIT_VERIFICATION",
        "建议复核",
        [{"toolName": "estimate_profit", "status": "success", "argsSummary": {"price": 110}}],
    ),
    _Scenario(
        "risk_verification",
        "RISK_VERIFICATION",
        "建议复核",
        [
            {
                "toolName": "evaluate_risk_rules",
                "status": "success",
                "argsSummary": {
                    "current_price": 120,
                    "cost_price": 80,
                    "candidate_price": 110,
                    "min_profit_rate": 0.2,
                    "max_discount_rate": 0.5,
                    "min_price": 90,
                    "max_price": 150,
                    "force_manual_review": False,
                },
            }
        ],
    ),
    _Scenario("market_weak_signal", "MARKET_WEAK_SIGNAL", "建议复核", []),
    _Scenario(
        "tool_failure",
        "CONSERVATIVE_DOWNGRADE",
        "不建议确认",
        [{"toolName": "estimate_profit", "status": "error", "errorType": "TOOL_EXECUTION_ERROR"}],
    ),
    _Scenario(
        "midpoint",
        "PRICE_DISAGREEMENT",
        "建议复核",
        [{"toolName": "estimate_profit", "status": "success"}],
        selected_agent=None,
        selected_price=None,
    ),
    _Scenario("audit_disabled", "PROFIT_VERIFICATION", "建议复核", []),
]


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[item.name for item in SCENARIOS])
def test_agentic_workflow_acceptance_paths(monkeypatch, scenario: _Scenario):
    db = _build_session()
    task = _create_task(db, 950 + SCENARIOS.index(scenario))

    monkeypatch.setattr(
        "app.services.orchestration_service.build_crewai_llm",
        lambda **kwargs: SimpleNamespace(model="fake-model"),
    )
    monkeypatch.setattr(
        "app.services.orchestration_service.build_pricing_crew",
        lambda **kwargs: _fake_bundle(scenario),
    )

    captured_results = []
    service = OrchestrationService(db, progress_service=SimpleNamespace(publish_sync=lambda *args, **kwargs: None))
    service.result_tool = SimpleNamespace(write_final_result=captured_results.append)

    result = service.run(_payload(task.id))

    manager_log = (
        db.query(AgentRunLog)
        .filter(
            AgentRunLog.task_id == task.id,
            AgentRunLog.display_order == 4,
            AgentRunLog.stage == "completed",
        )
        .one()
    )
    raw = manager_log.raw_output_json
    opinion = raw["agentOpinion"]
    tool_audit = raw.get("toolAudit", [])

    assert manager_log.stage == "completed"
    assert manager_log.display_order == 4
    assert opinion["agentCode"] == "MANAGER_COORDINATOR"
    assert opinion["decision"]["arbitrationDecision"] == scenario.decision
    assert result.result_summary.startswith(scenario.summary_prefix)
    assert captured_results == [result]
    assert tool_audit == scenario.audit
    if scenario.name == "midpoint":
        assert raw.get("selectedAgent") is None
        assert raw.get("selectedPrice") is None
    if scenario.name == "audit_disabled":
        assert scenario.decision != "FAST_PATH"
