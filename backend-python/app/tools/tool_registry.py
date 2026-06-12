"""Registry for CrewAI function-calling tools and role-scoped permissions."""

from dataclasses import dataclass
from typing import Any

from app.tools.crewai_tools import (
    estimate_profit,
    estimate_sales_volume,
    evaluate_risk_rules,
    query_competitor_summary,
    summarize_product_data,
)


@dataclass(frozen=True)
class ToolRegistration:
    name: str
    tool: Any
    allowed_agents: frozenset[str]
    timeout_seconds: int = 5
    audit_summary_fields: tuple[str, ...] = ()


_TOOL_REGISTRATIONS: tuple[ToolRegistration, ...] = (
    ToolRegistration(
        name="summarize_product_data",
        tool=summarize_product_data,
        allowed_agents=frozenset({"DATA_ANALYSIS"}),
        audit_summary_fields=("productId", "currentPrice", "monthlySales"),
    ),
    ToolRegistration(
        name="estimate_sales_volume",
        tool=estimate_sales_volume,
        allowed_agents=frozenset({"DATA_ANALYSIS", "MANAGER_COORDINATOR"}),
        audit_summary_fields=("estimated_sales",),
    ),
    ToolRegistration(
        name="estimate_profit",
        tool=estimate_profit,
        allowed_agents=frozenset({"DATA_ANALYSIS", "MANAGER_COORDINATOR"}),
        audit_summary_fields=("estimated_profit",),
    ),
    ToolRegistration(
        name="query_competitor_summary",
        tool=query_competitor_summary,
        allowed_agents=frozenset({"MARKET_INTEL"}),
        audit_summary_fields=("summary",),
    ),
    ToolRegistration(
        name="evaluate_risk_rules",
        tool=evaluate_risk_rules,
        allowed_agents=frozenset({"RISK_CONTROL", "MANAGER_COORDINATOR"}),
        audit_summary_fields=(
            "is_pass",
            "safe_floor_price",
            "suggested_price",
            "risk_level",
            "need_manual_review",
            "margin",
        ),
    ),
)

_REGISTRY_BY_NAME: dict[str, ToolRegistration] = {item.name: item for item in _TOOL_REGISTRATIONS}


def get_tools_for_agent(agent_code: str) -> list[Any]:
    return [item.tool for item in _TOOL_REGISTRATIONS if agent_code in item.allowed_agents]


def allowed_tool_names(agent_code: str | None) -> set[str]:
    if not agent_code:
        return set()
    return {item.name for item in _TOOL_REGISTRATIONS if agent_code in item.allowed_agents}


def is_tool_allowed(agent_code: str | None, tool_name: str) -> bool:
    return tool_name in allowed_tool_names(agent_code)


def registered_tool_names() -> set[str]:
    return set(_REGISTRY_BY_NAME)


def get_tool_registration(tool_name: str) -> ToolRegistration | None:
    return _REGISTRY_BY_NAME.get(tool_name)
