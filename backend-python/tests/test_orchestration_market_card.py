from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.crew import crew_factory
from app.schemas.agent import DataAgentOutput, ManagerAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.services.orchestration_service import OrchestrationService


def _build_payload() -> SimpleNamespace:
    return SimpleNamespace(
        product=SimpleNamespace(
            product_id=1001,
            product_name="coffee",
            category_name="beverage",
            current_price=Decimal("29.90"),
        )
    )


def test_build_market_card_uses_competitor_samples():
    parsed = {
        "thinking": "market-thinking",
        "source": "TMALL_CSV",
        "sourceStatus": "OK",
        "validCompetitorCount": 7,
        "dataQuality": "HIGH",
        "qualityReasons": ["有效竞品数不少于5个"],
        "pricingPosition": "接近市场主流带",
        "competitorSamples": 7,
        "marketFloor": 19.9,
        "marketCeiling": 39.9,
        "suggestedPrice": 29.9,
        "confidence": 0.86,
        "summary": "market-summary",
    }

    thinking, evidence, suggestion = OrchestrationService._build_market_card(parsed)

    assert thinking == "market-thinking"
    assert evidence[0]["value"] == 7
    assert suggestion["recommendedPrice"] == 29.9
    assert suggestion["dataQuality"] == "HIGH"
    assert suggestion["pricingPosition"] == "接近市场主流带"


def test_build_market_card_does_not_fake_missing_sales_weighted_fields_as_zero():
    parsed = {
        "thinking": "market-thinking",
        "source": "TMALL_CSV",
        "sourceStatus": "OK",
        "validCompetitorCount": 8,
        "dataQuality": "HIGH",
        "qualityReasons": ["有效竞品数不少于5个"],
        "competitorSamples": 8,
        "marketFloor": 19.9,
        "marketMedian": 29.9,
        "marketCeiling": 39.9,
        "marketAverage": 28.8,
        "suggestedPrice": 29.9,
        "confidence": 0.86,
        "summary": "market-summary",
    }

    _, evidence, suggestion = OrchestrationService._build_market_card(parsed)

    labels = [item["label"] for item in evidence]
    assert "销量加权均价" not in labels
    assert "销量加权中位价" not in labels
    assert suggestion["salesWeightedAverage"] is None


def test_precompute_competitor_summary_includes_failure_metadata(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_id"] == 1001
            return {
                "sourceStatus": "FAILED",
                "source": "TMALL_CSV",
                "message": "token expired",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品来源: TMALL_CSV" in summary
    assert "竞品状态: FAILED" in summary
    assert "状态说明: token expired" in summary
    assert "原始样本数: 0" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples 输出 0" in summary
    assert "marketFloor 与 marketCeiling 输出 0" in summary
    assert "confidence 必须 <= 0.3" in summary
    assert "suggestedPrice 输出 0" in summary


def test_precompute_competitor_summary_includes_unconfigured_metadata(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["category_name"] == "beverage"
            return {
                "sourceStatus": "UNCONFIGURED",
                "source": "TMALL_CSV",
                "message": "missing cookie",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品来源: TMALL_CSV" in summary
    assert "竞品状态: UNCONFIGURED" in summary
    assert "状态说明: missing cookie" in summary
    assert "原始样本数: 0" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples 输出 0" in summary
    assert "marketFloor 与 marketCeiling 输出 0" in summary
    assert "confidence 必须 <= 0.3" in summary
    assert "suggestedPrice 输出 0" in summary


def test_precompute_competitor_summary_adds_no_data_guardrail_when_status_ok_but_empty(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_id"] == 1001
            return {
                "sourceStatus": "OK",
                "source": "TMALL_CSV",
                "message": "empty result",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品状态: OK" in summary
    assert "状态说明: empty result" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples 输出 0" in summary
    assert "marketFloor 与 marketCeiling 输出 0" in summary
    assert "confidence 必须 <= 0.3" in summary
    assert "suggestedPrice 输出 0" in summary


def test_build_pricing_crew_threads_no_data_suggested_price_guardrail_into_market_task_description(monkeypatch):
    payload = SimpleNamespace(
        product=SimpleNamespace(
            product_id=1001,
            product_name="coffee",
            category_name="beverage",
            current_price=Decimal("29.90"),
            cost_price=Decimal("16.80"),
        ),
        strategy_goal="profit",
        baseline_sales=120,
        baseline_profit=Decimal("1200.00"),
        constraints={},
        metrics=[],
        traffic=[],
    )

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            return {
                "sourceStatus": "FAILED",
                "source": "TMALL_CSV",
                "message": "token expired",
                "rawItemCount": 0,
                "competitors": [],
            }

    class _FakeTask:
        instances = []

        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs
            _FakeTask.instances.append(self)

    class _FakeCrew:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)
    monkeypatch.setattr(crew_factory, "_precompute_data_summary", lambda _payload: "data-summary")
    monkeypatch.setattr(crew_factory, "_build_metrics_summary", lambda _payload: "metrics-summary")
    monkeypatch.setattr(crew_factory, "_build_constraints_text", lambda _constraints: "constraints-summary")
    monkeypatch.setattr(
        crew_factory,
        "build_crewai_agents",
        lambda **kwargs: {
            "DATA_ANALYSIS": "data-agent",
            "MARKET_INTEL": "market-agent",
            "RISK_CONTROL": "risk-agent",
            "MANAGER_COORDINATOR": "manager-agent",
        },
    )
    monkeypatch.setattr(crew_factory, "Task", _FakeTask)
    monkeypatch.setattr(crew_factory, "Crew", _FakeCrew)

    summary = crew_factory._precompute_competitor_summary(payload)
    crew_factory.build_pricing_crew(payload, analysis_llm=object(), manager_llm=object())

    market_task = next(task for task in _FakeTask.instances if task.kwargs["agent"] == "market-agent")
    market_description = market_task.kwargs["description"]

    assert "sourceStatus != OK 或 competitorSamples == 0" in summary
    assert "suggestedPrice 输出 0" in summary
    assert "suggestedPrice 输出 0" in market_description


def test_precompute_competitor_summary_includes_ok_metadata_and_details(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_title"] == "coffee"
            return {
                "sourceStatus": "OK",
                "source": "TMALL_CSV",
                "message": "ok",
                "rawItemCount": 2,
                "filteredItemCount": 2,
                "validCompetitorCount": 2,
                "marketFloor": 26.5,
                "marketMedian": 29.15,
                "marketCeiling": 31.8,
                "marketAverage": 29.15,
                "dataQuality": "LOW",
                "qualityReasons": ["有效竞品数不足3个"],
                "competitors": [
                    {
                        "competitorName": "A",
                        "price": 26.5,
                        "sourcePlatform": "taobao",
                        "promotionTag": "coupon",
                    },
                    {
                        "competitorName": "B",
                        "price": 31.8,
                        "sourcePlatform": "tmall",
                        "promotionTag": "full-reduction",
                    },
                ],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品来源: TMALL_CSV" in summary
    assert "竞品状态: OK" in summary
    assert "状态说明: ok" in summary
    assert "原始样本数: 2" in summary
    assert "竞品样本数: 2" in summary
    assert "A" in summary
    assert "B" in summary

def test_precompute_competitor_summary_adds_low_quality_guardrail(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            return {
                "sourceStatus": "OK",
                "source": "TMALL_CSV",
                "message": "request succeeded",
                "rawItemCount": 4,
                "filteredItemCount": 2,
                "validCompetitorCount": 2,
                "marketFloor": 199.0,
                "marketMedian": 209.0,
                "marketCeiling": 219.0,
                "marketAverage": 209.0,
                "dataQuality": "LOW",
                "qualityReasons": ["有效竞品数不足3个"],
                "competitors": [
                    {"competitorName": "A", "price": 199.0, "sourcePlatform": "taobao"},
                    {"competitorName": "B", "price": 219.0, "sourcePlatform": "tmall"},
                ],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "数据质量: LOW" in summary
    assert "validCompetitorCount < 3" in summary
    assert "不得输出激进的市场结论" in summary


def test_build_pricing_crew_market_task_requires_sales_weighted_fields(monkeypatch):
    payload = SimpleNamespace(
        product=SimpleNamespace(
            product_id=1001,
            product_name="coffee",
            category_name="beverage",
            current_price=Decimal("29.90"),
            cost_price=Decimal("16.80"),
        ),
        strategy_goal="profit",
        baseline_sales=120,
        baseline_profit=Decimal("1200.00"),
        constraints={},
        metrics=[],
        traffic=[],
    )

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            return {
                "sourceStatus": "OK",
                "source": "TMALL_CSV",
                "message": "ok",
                "rawItemCount": 1,
                "filteredItemCount": 1,
                "validCompetitorCount": 1,
                "marketFloor": 29.9,
                "marketMedian": 29.9,
                "marketCeiling": 29.9,
                "marketAverage": 29.9,
                "salesWeightedAverage": 29.9,
                "salesWeightedMedian": 29.9,
                "competitors": [{"competitorName": "A", "price": 29.9, "sourcePlatform": "tmall"}],
            }

    class _FakeTask:
        instances = []

        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs
            _FakeTask.instances.append(self)

    class _FakeCrew:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.kwargs = kwargs

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)
    monkeypatch.setattr(crew_factory, "_precompute_data_summary", lambda _payload: "data-summary")
    monkeypatch.setattr(crew_factory, "_build_metrics_summary", lambda _payload: "metrics-summary")
    monkeypatch.setattr(crew_factory, "_build_constraints_text", lambda _constraints: "constraints-summary")
    monkeypatch.setattr(
        crew_factory,
        "build_crewai_agents",
        lambda **kwargs: {
            "DATA_ANALYSIS": "data-agent",
            "MARKET_INTEL": "market-agent",
            "RISK_CONTROL": "risk-agent",
            "MANAGER_COORDINATOR": "manager-agent",
        },
    )
    monkeypatch.setattr(crew_factory, "Task", _FakeTask)
    monkeypatch.setattr(crew_factory, "Crew", _FakeCrew)

    crew_factory.build_pricing_crew(payload, analysis_llm=object(), manager_llm=object())

    market_task = next(task for task in _FakeTask.instances if task.kwargs["agent"] == "market-agent")
    assert '"salesWeightedAverage"' in market_task.kwargs["expected_output"]
    assert '"salesWeightedMedian"' in market_task.kwargs["expected_output"]
    assert "没有数据时填 null，不要写 0 占位" in market_task.kwargs["description"]



def test_market_agent_output_accepts_competitor_samples_alias():
    parsed = MarketAgentOutput.model_validate(
        {
            "suggestedPrice": "29.90",
            "marketFloor": "19.90",
            "marketCeiling": "39.90",
            "marketMedian": "29.15",
            "marketAverage": "29.15",
            "confidence": 0.88,
            "thinking": "market-thinking",
            "summary": "ok",
            "competitorSamples": 5,
        }
    )

    assert parsed.competitor_samples == 5

    old_alias = "simulated" + "Samples"
    with pytest.raises(ValidationError):
        MarketAgentOutput.model_validate(
            {
                "suggestedPrice": "29.90",
                "marketFloor": "19.90",
                "marketCeiling": "39.90",
                "marketMedian": "29.15",
                "marketAverage": "29.15",
                "confidence": 0.88,
                "thinking": "market-thinking",
                "summary": "ok",
                old_alias: 5,
            }
        )


def test_agent_output_models_preserve_runtime_fields_by_alias():
    data_dumped = DataAgentOutput.model_validate(
        {
            "suggestedPrice": "29.90",
            "suggestedMinPrice": "27.90",
            "suggestedMaxPrice": "31.90",
            "expectedSales": 120,
            "expectedProfit": "980.00",
            "confidence": 0.82,
            "thinking": "data-thinking",
            "summary": "data-summary",
        }
    ).model_dump(by_alias=True)
    assert data_dumped["thinking"] == "data-thinking"

    market_dumped = MarketAgentOutput.model_validate(
        {
            "suggestedPrice": "29.90",
            "marketFloor": "19.90",
            "marketCeiling": "39.90",
            "marketMedian": "29.15",
            "marketAverage": "29.15",
            "confidence": 0.88,
            "confidenceScore": 0.75,
            "marketScore": 75.0,
            "thinking": "market-thinking",
            "summary": "market-summary",
            "competitorSamples": 3,
            "competitors": [
                {"competitorName": "A", "price": "29.90", "sourcePlatform": "taobao"},
            ],
        }
    ).model_dump(by_alias=True)
    assert market_dumped["thinking"] == "market-thinking"
    assert market_dumped["marketMedian"] == Decimal("29.15")
    assert market_dumped["marketAverage"] == Decimal("29.15")
    assert market_dumped["competitors"][0]["competitorName"] == "A"
    assert market_dumped["confidenceScore"] == 0.75
    assert market_dumped["marketScore"] == 75.0

    risk_dumped = RiskAgentOutput.model_validate(
        {
            "isPass": False,
            "safeFloorPrice": "21.00",
            "suggestedPrice": "29.90",
            "riskLevel": "HIGH",
            "needManualReview": True,
            "thinking": "risk-thinking",
            "summary": "risk-summary",
        }
    ).model_dump(by_alias=True)
    assert risk_dumped["thinking"] == "risk-thinking"

    manager_dumped = ManagerAgentOutput.model_validate(
        {
            "finalPrice": "29.90",
            "expectedSales": 120,
            "expectedProfit": "980.00",
            "profitGrowth": "180.00",
            "executeStrategy": "人工审核",
            "isPass": False,
            "thinking": "manager-thinking",
            "resultSummary": "manager-summary",
            "suggestedMinPrice": "27.90",
            "suggestedMaxPrice": "31.90",
        }
    ).model_dump(by_alias=True)
    assert manager_dumped["thinking"] == "manager-thinking"


def test_agent_output_models_reject_unsafe_values():
    with pytest.raises(ValidationError):
        DataAgentOutput.model_validate(
            {
                "suggestedPrice": "29.90",
                "suggestedMinPrice": "27.90",
                "suggestedMaxPrice": "31.90",
                "expectedSales": 120,
                "expectedProfit": "980.00",
                "confidence": 95,
                "thinking": "data-thinking",
                "summary": "data-summary",
            }
        )

    with pytest.raises(ValidationError):
        RiskAgentOutput.model_validate(
            {
                "isPass": False,
                "safeFloorPrice": "21.00",
                "suggestedPrice": "29.90",
                "riskLevel": "MEDIUM",
                "needManualReview": True,
                "thinking": "risk-thinking",
                "summary": "risk-summary",
            }
        )

    with pytest.raises(ValidationError):
        ManagerAgentOutput.model_validate(
            {
                "finalPrice": "29.90",
                "expectedSales": 120,
                "expectedProfit": "980.00",
                "profitGrowth": "180.00",
                "executeStrategy": "AUTO_EXECUTE",
                "isPass": False,
                "thinking": "manager-thinking",
                "resultSummary": "manager-summary",
                "suggestedMinPrice": "27.90",
                "suggestedMaxPrice": "31.90",
            }
        )
