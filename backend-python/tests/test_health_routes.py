from app.api import health as health_module


class _FakeDb:
    def execute(self, *_args, **_kwargs):
        return 1

    def close(self):
        return None


class _FakeWorker:
    def __init__(self, *, started: bool, ready: bool):
        self._snapshot = {
            "started": started,
            "ready": ready,
            "prefetch": 1,
            "maxRetry": 3,
            "workerConcurrency": 2,
            "activeConsumers": 2 if ready else 0,
        }
        self.ready = ready

    def snapshot(self):
        return self._snapshot


def test_health_ready_reports_rabbitmq_ready_when_worker_is_ready(monkeypatch):
    monkeypatch.setattr(health_module, "SessionLocal", lambda: _FakeDb())
    monkeypatch.setattr(health_module, "get_rabbitmq_worker_service", lambda: _FakeWorker(started=True, ready=True))

    response = health_module.health_ready()

    assert response["status"] == "ok"
    assert response["dbOk"] is True
    assert response["rabbitmq"] == "ok"
    assert response["worker"]["workerConcurrency"] == 2
    assert response["worker"]["activeConsumers"] == 2


def test_health_ready_reports_degraded_when_worker_not_ready(monkeypatch):
    monkeypatch.setattr(health_module, "SessionLocal", lambda: _FakeDb())
    monkeypatch.setattr(health_module, "get_rabbitmq_worker_service", lambda: _FakeWorker(started=True, ready=False))

    response = health_module.health_ready()

    assert response["status"] == "degraded"
    assert response["rabbitmq"] == "down"
    assert response["worker"]["activeConsumers"] == 0
