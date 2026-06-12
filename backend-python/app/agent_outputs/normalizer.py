"""Normalize and validate raw Agent JSON contracts."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.schemas.agent import DataAgentOutput, ManagerAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY

AGENT_OUTPUT_MODELS = {
    "DATA_ANALYSIS": DataAgentOutput,
    "MARKET_INTEL": MarketAgentOutput,
    "RISK_CONTROL": RiskAgentOutput,
    "MANAGER_COORDINATOR": ManagerAgentOutput,
}


class AgentOutputValidationError(RuntimeError):
    def __init__(self, agent_code: str, message: str):
        super().__init__(message)
        self.agent_code = agent_code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.agent_code}] {self.message}"


def normalize_optional_text(val: Any) -> str | None:
    text = str(val or "").strip()
    if not text:
        return None
    if text in {"-", "--", "—", "暂无", "暂无数据", "无", "N/A", "n/a", "null", "None"}:
        return None
    return text


def first_present(source: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def normalize_selected_agent(val: Any) -> str | None:
    text = normalize_optional_text(val)
    if text in {"DATA_ANALYSIS", "MARKET_INTEL", "RISK_CONTROL"}:
        return text
    return None


def normalize_manager_output_contract(parsed: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(parsed)
    strategy = normalize_optional_text(normalized.get("executeStrategy"))
    if strategy and strategy.strip().lower() in {"manual_review", "manual", "manual review"}:
        normalized["executeStrategy"] = MANUAL_REVIEW_STRATEGY
    elif strategy in {"人工复核", "人工审核"}:
        normalized["executeStrategy"] = MANUAL_REVIEW_STRATEGY

    opinion = normalized.get("agentOpinion")
    decision_type = normalize_optional_text(normalized.get("decisionType"))
    if isinstance(opinion, dict):
        opinion = dict(opinion)
        decision = opinion.get("decision")
        if isinstance(decision, dict):
            decision = dict(decision)
            nested_type = normalize_optional_text(decision.get("decisionType"))
            if nested_type:
                upper_type = nested_type.upper()
                if upper_type in {"FOLLOW", "OVERRIDE", "MERGE", "REJECT_ALL"}:
                    decision["decisionType"] = upper_type
                    decision_type = upper_type
            opinion["decision"] = decision
        normalized["agentOpinion"] = opinion

    selected_text = normalize_optional_text(first_present(normalized, "selectedAgent", "selectedOption"))
    selected_upper = selected_text.upper() if selected_text else ""
    merge_like = selected_upper in {"MERGE", "MERGED", "REJECT_ALL", "NULL", "NONE"} or selected_text in {
        "综合",
        "折中",
        "综合专家意见",
        "折中定价",
    }
    if merge_like or (decision_type or "").upper() in {"MERGE", "REJECT_ALL"}:
        normalized["selectedAgent"] = None
        normalized["selectedOption"] = None
        if isinstance(normalized.get("agentOpinion"), dict):
            relations = normalized["agentOpinion"].get("relations")
            if isinstance(relations, dict):
                relations = dict(relations)
                relations["selectedOpinionIds"] = []
                normalized["agentOpinion"]["relations"] = relations

    return normalized


def validate_agent_output(agent_code: str, parsed: dict[str, Any]) -> dict[str, Any]:
    model_cls = AGENT_OUTPUT_MODELS.get(agent_code)
    if model_cls is None:
        return parsed
    try:
        model = model_cls.model_validate(parsed)
    except ValidationError as exc:
        recovered = validate_without_untrusted_agent_opinion(model_cls, parsed)
        if recovered is not None:
            return recovered
        raise AgentOutputValidationError(agent_code, "输出结构校验失败") from exc
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


def validate_without_untrusted_agent_opinion(model_cls: type[Any], parsed: dict[str, Any]) -> dict[str, Any] | None:
    if "agentOpinion" not in parsed:
        return None
    sanitized = dict(parsed)
    sanitized.pop("agentOpinion", None)
    try:
        model = model_cls.model_validate(sanitized)
    except ValidationError:
        return None
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")

