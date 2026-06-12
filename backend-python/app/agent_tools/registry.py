"""Role-scoped agent tool registry facade."""

from app.tools.tool_registry import (
    ToolRegistration,
    allowed_tool_names,
    get_tool_registration,
    get_tools_for_agent,
    is_tool_allowed,
    registered_tool_names,
)

__all__ = [
    "ToolRegistration",
    "allowed_tool_names",
    "get_tool_registration",
    "get_tools_for_agent",
    "is_tool_allowed",
    "registered_tool_names",
]
