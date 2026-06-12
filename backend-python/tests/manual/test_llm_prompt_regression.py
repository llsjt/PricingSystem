"""Manual prompt regression cases for real LLM runs.

Run only when a real audited LLM endpoint is available:

    RUN_LLM_PROMPT_REGRESSION=1 python -m pytest tests/manual/test_llm_prompt_regression.py -q
"""

from __future__ import annotations

import os
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LLM_PROMPT_REGRESSION") != "1",
    reason="manual real-LLM regression; set RUN_LLM_PROMPT_REGRESSION=1 to run",
)


def _payload(case_name: str, *, current: str, cost: str, baseline_profit: str, strategy: str, constraints: dict) -> dict:
    return {
        "caseName": case_name,
        "strategyGoal": strategy,
        "constraints": constraints,
        "product": {"currentPrice": current, "costPrice": cost, "stock": 1000},
        "baselineSales": 100,
        "baselineProfit": baseline_profit,
        "metrics": [],
        "traffic": [],
    }


PROMPT_REGRESSION_DATASET = [
    _payload("normal_profit", current="99.00", cost="60.00", baseline_profit="3000.00", strategy="MAX_PROFIT", constraints={}),
    _payload("low_margin", current="19.90", cost="18.50", baseline_profit="120.00", strategy="MAX_PROFIT", constraints={}),
    _payload("below_safe_floor", current="29.90", cost="28.80", baseline_profit="200.00", strategy="MAX_PROFIT", constraints={"min_price": 30}),
    _payload("force_manual_review", current="88.00", cost="55.00", baseline_profit="2100.00", strategy="MAX_PROFIT", constraints={"force_manual_review": True}),
    _payload("clearance", current="49.00", cost="35.00", baseline_profit="900.00", strategy="CLEARANCE", constraints={"max_discount_rate": 0.2}),
    _payload("market_weak_signal", current="129.00", cost="90.00", baseline_profit="1800.00", strategy="MAX_PROFIT", constraints={"market_data_quality": "LOW"}),
    _payload("tight_min_max", current="59.00", cost="42.00", baseline_profit="850.00", strategy="MAX_PROFIT", constraints={"min_price": 55, "max_price": 62}),
    _payload("high_stock", current="39.90", cost="20.00", baseline_profit="1500.00", strategy="GROWTH", constraints={"stock_pressure": "HIGH"}),
    _payload("premium_position", current="299.00", cost="180.00", baseline_profit="5000.00", strategy="MAX_PROFIT", constraints={"brand_position": "PREMIUM"}),
    _payload("flash_sale_guarded", current="79.00", cost="50.00", baseline_profit="1600.00", strategy="PROMOTION", constraints={"max_discount_rate": 0.15}),
    _payload("cost_spike", current="119.00", cost="112.00", baseline_profit="700.00", strategy="MAX_PROFIT", constraints={"min_profit_rate": 0.08}),
    _payload("price_ceiling", current="199.00", cost="130.00", baseline_profit="3200.00", strategy="MAX_PROFIT", constraints={"max_price": 205}),
    _payload("loss_block", current="9.90", cost="10.50", baseline_profit="-50.00", strategy="CLEARANCE", constraints={}),
    _payload("stable_no_change", current="69.00", cost="45.00", baseline_profit="1800.00", strategy="STABLE", constraints={"max_price_change_rate": 0.03}),
    _payload("strong_discount_block", current="159.00", cost="80.00", baseline_profit="2600.00", strategy="PROMOTION", constraints={"max_discount_rate": 0.1}),
]


def test_manual_prompt_regression_dataset_has_required_coverage():
    assert len(PROMPT_REGRESSION_DATASET) == 15
    assert any(case["constraints"].get("force_manual_review") for case in PROMPT_REGRESSION_DATASET)
    assert any(Decimal(case["product"]["costPrice"]) > Decimal(case["product"]["currentPrice"]) for case in PROMPT_REGRESSION_DATASET)
    assert any(case["constraints"].get("max_discount_rate") for case in PROMPT_REGRESSION_DATASET)


def test_real_llm_prompt_regression_placeholder():
    # This test intentionally defines the manual gate without spending tokens in CI.
    assert os.getenv("LLM_API_KEY")

