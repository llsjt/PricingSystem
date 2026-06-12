"""Deterministic final decision guardrails for pricing results."""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.crew.protocols import CrewRunPayload
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY

SYSTEM_GUARDRAIL_MESSAGE = "[系统风控兜底已触发：最终定价违反了商家预设的风控约束]"
PROFIT_EPSILON = Decimal("0.01")


@dataclass(frozen=True)
class VerificationContext:
    payload: CrewRunPayload
    final_price: Decimal
    expected_profit: Decimal
    prior_outputs: dict[str, Any] | dict[int, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VerificationResult:
    is_pass: bool
    execute_strategy: str
    violation_reasons: list[str]
    reason_codes: list[str]
    audit_flags: dict[str, Any]


class FinalDecisionVerifier:
    """Verify final pricing output without trusting the LLM conclusion."""

    def verify(self, context: VerificationContext) -> VerificationResult:
        payload = context.payload
        constraints = _as_mapping(_read(payload, "constraints")) or {}
        final_price = money(context.final_price)
        expected_profit = money(context.expected_profit)
        cost_price = money(_read(_read(payload, "product"), "cost_price"))
        current_price = money(_read(_read(payload, "product"), "current_price"))
        baseline_profit = money(_read(payload, "baseline_profit"))

        reason_codes: list[str] = []
        violation_reasons: list[str] = []
        audit_flags: dict[str, Any] = {}

        def fail(code: str, reason: str) -> None:
            if code not in reason_codes:
                reason_codes.append(code)
                violation_reasons.append(reason)

        if final_price < cost_price:
            fail("PRICE_BELOW_COST", f"最终价 {final_price} 低于成本价 {cost_price}")

        if expected_profit <= baseline_profit:
            if baseline_profit - expected_profit <= PROFIT_EPSILON:
                audit_flags["profitEpsilonTouched"] = True
            fail("PROFIT_NOT_IMPROVED", f"预期利润 {expected_profit} 未高于基线利润 {baseline_profit}")

        min_price = _constraint_decimal(constraints, "min_price", "minPrice")
        if min_price is not None and final_price < min_price:
            fail("BELOW_MIN_PRICE", f"最终价 {final_price} 低于约束最低价 {min_price}")

        max_price = _constraint_decimal(constraints, "max_price", "maxPrice")
        if max_price is not None and final_price > max_price:
            fail("ABOVE_MAX_PRICE", f"最终价 {final_price} 高于约束最高价 {max_price}")

        max_discount_rate = _constraint_decimal(constraints, "max_discount_rate", "maxDiscountRate")
        if max_discount_rate is not None and current_price > 0 and final_price < current_price:
            discount_rate = (current_price - final_price) / current_price
            audit_flags["discountRate"] = str(discount_rate.quantize(Decimal("0.0001")))
            if discount_rate > max_discount_rate:
                fail("DISCOUNT_EXCEEDS_MAX_RATE", f"折扣率 {discount_rate:.4f} 超过最大折扣率 {max_discount_rate}")

        if _constraint_bool(constraints, "force_manual_review", "forceManualReview"):
            fail("FORCE_MANUAL_REVIEW", "商家约束要求强制人工审核")

        if _risk_agent_blocked(context.prior_outputs):
            fail("RISK_AGENT_BLOCKED", "风险控制 Agent 判定未通过")

        low_quality_market = _has_low_quality_market_data(context.prior_outputs)
        if low_quality_market:
            audit_flags["marketCeilingReferenceOnly"] = True
            audit_flags["lowQualityMarketData"] = True

        return VerificationResult(
            is_pass=not reason_codes,
            execute_strategy=MANUAL_REVIEW_STRATEGY,
            violation_reasons=violation_reasons,
            reason_codes=reason_codes,
            audit_flags=audit_flags,
        )


def append_guardrail_summary(summary: str, verification: VerificationResult) -> str:
    text = str(summary or "").strip()
    if verification.is_pass or SYSTEM_GUARDRAIL_MESSAGE in text:
        return text
    reasons = "；".join(verification.violation_reasons)
    suffix = SYSTEM_GUARDRAIL_MESSAGE if not reasons else f"{SYSTEM_GUARDRAIL_MESSAGE}：{reasons}"
    return f"{text}\n{suffix}" if text else suffix


def _read(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _constraint_decimal(constraints: dict[str, Any], *keys: str) -> Decimal | None:
    for key in keys:
        if key not in constraints or constraints[key] in (None, ""):
            continue
        try:
            return Decimal(str(constraints[key]))
        except (InvalidOperation, ValueError):
            return None
    return None


def _constraint_bool(constraints: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = constraints.get(key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "人工审核", "manual_review"}
    return False


def _iter_prior_outputs(prior_outputs: dict[str, Any] | dict[int, Any]) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for value in (prior_outputs or {}).values():
        if isinstance(value, dict):
            outputs.append(value)
    return outputs


def _risk_agent_blocked(prior_outputs: dict[str, Any] | dict[int, Any]) -> bool:
    for output in _iter_prior_outputs(prior_outputs):
        agent_code = str((output.get("agentOpinion") or {}).get("agentCode") or output.get("agentCode") or "")
        risk = _as_mapping((output.get("agentOpinion") or {}).get("risk"))
        raw_is_pass = output.get("isPass", risk.get("isPass"))
        if (agent_code == "RISK_CONTROL" or "safeFloorPrice" in output) and raw_is_pass is False:
            return True
    return False


def _has_low_quality_market_data(prior_outputs: dict[str, Any] | dict[int, Any]) -> bool:
    for output in _iter_prior_outputs(prior_outputs):
        opinion_market = _as_mapping((output.get("agentOpinion") or {}).get("market"))
        data_quality = str(output.get("dataQuality") or opinion_market.get("dataQuality") or "").upper()
        source_status = str(output.get("sourceStatus") or opinion_market.get("sourceStatus") or "").upper()
        if data_quality == "LOW" or (source_status and source_status != "OK"):
            return True
    return False
