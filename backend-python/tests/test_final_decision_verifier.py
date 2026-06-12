from decimal import Decimal
from types import SimpleNamespace

from app.domain.final_decision_verifier import (
    SYSTEM_GUARDRAIL_MESSAGE,
    FinalDecisionVerifier,
    VerificationContext,
    append_guardrail_summary,
)


def _payload(*, constraints: dict | None = None):
    return SimpleNamespace(
        constraints=constraints or {
            "min_price": "90.00",
            "max_price": "130.00",
            "max_discount_rate": "0.20",
            "force_manual_review": False,
        },
        product=SimpleNamespace(
            current_price=Decimal("120.00"),
            cost_price=Decimal("80.00"),
        ),
        baseline_profit=Decimal("500.00"),
    )


def _verify(final_price: str, expected_profit: str, *, constraints: dict | None = None, prior_outputs=None):
    return FinalDecisionVerifier().verify(
        VerificationContext(
            payload=_payload(constraints=constraints),
            final_price=Decimal(final_price),
            expected_profit=Decimal(expected_profit),
            prior_outputs=prior_outputs or {},
        )
    )


def test_verifier_blocks_price_below_cost_and_summary_appends_guardrail_reason():
    result = _verify("75.00", "600.00")

    assert result.is_pass is False
    assert "PRICE_BELOW_COST" in result.reason_codes
    assert SYSTEM_GUARDRAIL_MESSAGE in append_guardrail_summary("summary", result)


def test_verifier_blocks_non_improving_profit_and_records_epsilon_touch():
    result = _verify("110.00", "500.00")

    assert result.is_pass is False
    assert "PROFIT_NOT_IMPROVED" in result.reason_codes
    assert result.audit_flags["profitEpsilonTouched"] is True


def test_verifier_blocks_min_max_discount_force_manual_and_risk_agent():
    result = _verify(
        "85.00",
        "700.00",
        constraints={
            "min_price": "90.00",
            "max_price": "100.00",
            "max_discount_rate": "0.10",
            "force_manual_review": True,
        },
        prior_outputs={
            3: {
                "agentOpinion": {"agentCode": "RISK_CONTROL"},
                "isPass": False,
                "safeFloorPrice": "90.00",
            }
        },
    )

    assert result.is_pass is False
    assert {
        "BELOW_MIN_PRICE",
        "DISCOUNT_EXCEEDS_MAX_RATE",
        "FORCE_MANUAL_REVIEW",
        "RISK_AGENT_BLOCKED",
    }.issubset(set(result.reason_codes))


def test_verifier_records_low_quality_market_data_as_audit_flag_only():
    result = _verify(
        "110.00",
        "700.00",
        prior_outputs={
            2: {
                "agentOpinion": {
                    "agentCode": "MARKET_INTEL",
                    "market": {"dataQuality": "LOW", "sourceStatus": "EMPTY"},
                }
            }
        },
    )

    assert result.is_pass is True
    assert result.audit_flags["marketCeilingReferenceOnly"] is True
