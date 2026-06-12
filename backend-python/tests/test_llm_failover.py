from app.crew.crewai_runtime import LLMHttpError
from app.infra.llm_client import FailoverCrewAILLM


class _FakeLLM:
    model = "fake-model"
    provider = "openai-compatible"
    api_key = "fake-key"
    base_url = "https://example.com/v1"
    temperature = 0.2

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def call(self, *args, **kwargs):  # noqa: ANN002, ANN003
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def test_failover_llm_switches_to_backup_after_primary_429():
    primary = _FakeLLM(
        error=LLMHttpError(status_code=429, body="rate limited", url="https://primary.example.com/chat/completions")
    )
    backup = _FakeLLM(result="backup-result")

    llm = FailoverCrewAILLM(primary=primary, backup=backup)

    assert llm.call("prompt") == "backup-result"
    assert primary.calls == 1
    assert backup.calls == 1


def test_failover_llm_does_not_mask_non_retryable_error():
    primary = _FakeLLM(error=ValueError("bad prompt"))
    backup = _FakeLLM(result="backup-result")
    llm = FailoverCrewAILLM(primary=primary, backup=backup)

    try:
        llm.call("prompt")
    except ValueError as exc:
        assert "bad prompt" in str(exc)
    else:
        raise AssertionError("expected non-retryable error")
    assert backup.calls == 0
