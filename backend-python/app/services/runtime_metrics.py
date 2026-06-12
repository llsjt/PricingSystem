"""In-process runtime counters for operational health snapshots."""

from threading import Lock


class RuntimeMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = {
            "casConflictCount": 0,
            "retryPublishFailureCount": 0,
            "progressPublishFailureCount": 0,
            "consumerRetryCount": 0,
            "llmTimeoutCount": 0,
            "manualReviewWithoutResultCount": 0,
            "sseTerminalLatencyMs": 0,
        }

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] = int(self._counters.get(name, 0)) + int(amount)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)


_runtime_metrics = RuntimeMetrics()


def get_runtime_metrics() -> RuntimeMetrics:
    return _runtime_metrics
