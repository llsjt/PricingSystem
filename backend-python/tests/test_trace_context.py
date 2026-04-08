import logging

from app.core.logger import TraceContextFilter
from app.core.trace_context import bind_trace_context


def test_trace_context_filter_injects_trace_and_task_identifiers():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )

    trace_filter = TraceContextFilter()
    with bind_trace_context(trace_id="trace-123", task_id=89):
        assert trace_filter.filter(record) is True

    assert record.trace_id == "trace-123"
    assert record.task_id == "89"
