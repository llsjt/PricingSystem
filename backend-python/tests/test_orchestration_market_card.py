from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.crew import crew_factory
from app.schemas.agent import MarketAgentOutput
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
        "source": "SNAPSHOT",
        "sourceStatus": "OK",
        "validCompetitorCount": 7,
        "dataQuality": "HIGH",
        "qualityReasons": ["valid competitors >= 5"],
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


def test_precompute_competitor_summary_includes_failure_metadata(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_id"] == 1001
            return {
                "sourceStatus": "FAILED",
                "source": "SNAPSHOT",
                "message": "token expired",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品来源: SNAPSHOT" in summary
    assert "竞品状态: FAILED" in summary
    assert "状态说明: token expired" in summary
    assert "原始样本数: 0" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples=0" in summary
    assert "marketFloor=0" in summary
    assert "marketCeiling=0" in summary
    assert "confidence <= 0.3" in summary
    assert "suggestedPrice=0" in summary


def test_precompute_competitor_summary_includes_unconfigured_metadata(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["category_name"] == "beverage"
            return {
                "sourceStatus": "UNCONFIGURED",
                "source": "SNAPSHOT",
                "message": "missing cookie",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品来源: SNAPSHOT" in summary
    assert "竞品状态: UNCONFIGURED" in summary
    assert "状态说明: missing cookie" in summary
    assert "原始样本数: 0" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples=0" in summary
    assert "marketFloor=0" in summary
    assert "marketCeiling=0" in summary
    assert "confidence <= 0.3" in summary
    assert "suggestedPrice=0" in summary


def test_precompute_competitor_summary_adds_no_data_guardrail_when_status_ok_but_empty(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_id"] == 1001
            return {
                "sourceStatus": "OK",
                "source": "SNAPSHOT",
                "message": "empty result",
                "rawItemCount": 0,
                "competitors": [],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "竞品状态: OK" in summary
    assert "状态说明: empty result" in summary
    assert "竞品样本数: 0" in summary
    assert "competitorSamples=0" in summary
    assert "marketFloor=0" in summary
    assert "marketCeiling=0" in summary
    assert "confidence <= 0.3" in summary
    assert "suggestedPrice=0" in summary


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
                "source": "SNAPSHOT",
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

    assert "sourceStatus != OK or competitorSamples == 0" in summary
    assert "suggestedPrice=0" in summary
    assert "suggestedPrice=0" in market_description


def test_precompute_competitor_summary_includes_ok_metadata_and_details(monkeypatch):
    payload = _build_payload()

    class _FakeService:
        def get_competitor_result(self, **kwargs):  # noqa: ANN003
            assert kwargs["product_title"] == "coffee"
            return {
                "sourceStatus": "OK",
                "source": "SNAPSHOT",
                "message": "ok",
                "rawItemCount": 2,
                "filteredItemCount": 2,
                "validCompetitorCount": 2,
                "marketFloor": 26.5,
                "marketMedian": 29.15,
                "marketCeiling": 31.8,
                "marketAverage": 29.15,
                "dataQuality": "LOW",
                "qualityReasons": ["valid competitors < 3"],
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

    assert "竞品来源: SNAPSHOT" in summary
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
                "source": "SNAPSHOT",
                "message": "request succeeded",
                "rawItemCount": 4,
                "filteredItemCount": 2,
                "validCompetitorCount": 2,
                "marketFloor": 199.0,
                "marketMedian": 209.0,
                "marketCeiling": 219.0,
                "marketAverage": 209.0,
                "dataQuality": "LOW",
                "qualityReasons": ["valid competitors < 3"],
                "competitors": [
                    {"competitorName": "A", "price": 199.0, "sourcePlatform": "taobao"},
                    {"competitorName": "B", "price": 219.0, "sourcePlatform": "tmall"},
                ],
            }

    monkeypatch.setattr(crew_factory, "CompetitorService", _FakeService)

    summary = crew_factory._precompute_competitor_summary(payload)

    assert "数据质量: LOW" in summary
    assert "validCompetitorCount < 3" in summary
    assert "do not output an aggressive market conclusion" in summary


def test_market_agent_output_accepts_competitor_samples_alias():
    parsed = MarketAgentOutput.model_validate(
        {
            "suggestedPrice": "29.90",
            "marketFloor": "19.90",
            "marketCeiling": "39.90",
            "confidence": 0.88,
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
                "confidence": 0.88,
                "summary": "ok",
                old_alias: 5,
            }
        )
