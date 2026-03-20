from __future__ import annotations

from fastapi.testclient import TestClient

from pricing_crew.server import app, workflow_service
from pricing_crew.schemas import (
    AnalysisRequest,
    CompetitorData,
    ProductBase,
    RiskData,
    SalesData,
)


client = TestClient(app)


def _sample_request_payload() -> dict:
    request = AnalysisRequest(
        task_id="API_SMOKE",
        product=ProductBase(
            product_id="P100",
            product_name="API Product",
            category="Electronics",
            current_price=99.0,
            cost=60.0,
            stock=200,
        ),
        sales_data=SalesData(
            sales_history_7d=[10, 12, 11, 13, 12, 14, 15],
            sales_history_30d=[12] * 30,
            sales_history_90d=[11] * 90,
        ),
        competitor_data=CompetitorData(competitors=[]),
        risk_data=RiskData(min_profit_margin=0.15),
    )
    return request.model_dump(mode="json")


def test_health_endpoint():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


def test_manager_decision_endpoint():
    resp = client.post("/agents/manager-decision", json=_sample_request_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"success", "failed"}
    if body["status"] == "success":
        assert body["result"]["decision"] in {"maintain", "discount", "increase"}


def test_start_task_endpoint(monkeypatch):
    called = {"ok": False}

    async def fake_execute_task(task_id, product_ids, strategy_goal, constraints):
        called["ok"] = True

    monkeypatch.setattr(workflow_service, "execute_task", fake_execute_task)

    payload = {
        "task_id": 123,
        "product_ids": [1, 2],
        "strategy_goal": "MAX_PROFIT",
        "constraints": "",
    }
    resp = client.post("/api/decision/start", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert isinstance(body["data"], int)
