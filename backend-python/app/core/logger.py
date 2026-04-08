from __future__ import annotations

import logging

from app.core.trace_context import current_trace_context


class TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        context = current_trace_context()
        record.trace_id = context.trace_id
        record.task_id = context.task_id
        return True


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.addFilter(TraceContextFilter())
        return

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] traceId=%(trace_id)s taskId=%(task_id)s %(name)s - %(message)s",
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(TraceContextFilter())
