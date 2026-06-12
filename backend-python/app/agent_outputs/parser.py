"""JSON extraction and syntactic validation for Agent outputs."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.agent.definitions import get_agent_meta
from app.agent_outputs.normalizer import AgentOutputValidationError, normalize_manager_output_contract, validate_agent_output
from app.crew.crewai_runtime import extract_json_object
from app.schemas.agent import AgentOpinionV1


def parse_and_validate_output(*, order: int, raw: str) -> dict[str, Any]:
    meta = get_agent_meta(order)
    parsed = extract_json_object(raw)
    if not parsed:
        raise AgentOutputValidationError(meta["code"], "输出解析失败")
    sanitized = dict(parsed)
    if meta["code"] == "MANAGER_COORDINATOR":
        sanitized = normalize_manager_output_contract(sanitized)
    provided_opinion = None
    for key in list(sanitized.keys()):
        normalized_key = "".join(ch for ch in str(key).lower() if ch.isalnum())
        if normalized_key != "agentopinion":
            continue
        if provided_opinion is None:
            provided_opinion = sanitized.pop(key)
        else:
            sanitized.pop(key, None)
    validated = validate_agent_output(meta["code"], sanitized)
    if isinstance(provided_opinion, dict):
        try:
            opinion = AgentOpinionV1.model_validate(provided_opinion)
        except ValidationError:
            pass
        else:
            validated["agentOpinion"] = opinion.model_dump(by_alias=True, exclude_none=True, mode="json")
    return validated

