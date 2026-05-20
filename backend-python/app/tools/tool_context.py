"""Tool execution context shared through contextvars during an agent run."""

import contextvars
from dataclasses import dataclass, field
from typing import Any

from app.crew.protocols import CrewRunPayload


@dataclass
class ToolContext:
    payload: CrewRunPayload
    task_id: int
    execution_id: str | None
    agent_code: str
    precomputed_competitor_summary: str | None = None
    tool_audit_logs: list[dict[str, Any]] = field(default_factory=list)


active_tool_context: contextvars.ContextVar[ToolContext | None] = contextvars.ContextVar(
    "active_tool_context",
    default=None,
)
