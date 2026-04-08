from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator


_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="-")
_task_id_var: ContextVar[str] = ContextVar("task_id", default="-")


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    task_id: str


def current_trace_context() -> TraceContext:
    return TraceContext(
        trace_id=_trace_id_var.get() or "-",
        task_id=_task_id_var.get() or "-",
    )


@contextmanager
def bind_trace_context(trace_id: str | None = None, task_id: int | str | None = None) -> Iterator[TraceContext]:
    trace_token: Token[str] | None = None
    task_token: Token[str] | None = None
    if trace_id is not None:
        trace_token = _trace_id_var.set(str(trace_id).strip() or "-")
    if task_id is not None:
        task_token = _task_id_var.set(str(task_id).strip() or "-")
    try:
        yield current_trace_context()
    finally:
        if task_token is not None:
            _task_id_var.reset(task_token)
        if trace_token is not None:
            _trace_id_var.reset(trace_token)
