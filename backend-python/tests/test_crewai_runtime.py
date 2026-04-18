from app.core.config import get_settings
from app.crew.crewai_runtime import build_crewai_llm, debug_log, is_debug_logging_enabled


def _set_minimal_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL", "default-model")


def test_build_crewai_llm_uses_configured_model_for_fast_profile(monkeypatch):
    _set_minimal_llm_env(monkeypatch)
    get_settings.cache_clear()

    llm = build_crewai_llm(profile="fast")

    assert llm.model == "default-model"


def test_debug_log_respects_crewai_debug_flag(monkeypatch, capsys):
    _set_minimal_llm_env(monkeypatch)
    monkeypatch.setenv("CREWAI_DEBUG_LOGS", "false")
    get_settings.cache_clear()
    assert is_debug_logging_enabled() is False
    debug_log("should_not_print")
    captured = capsys.readouterr()
    assert "should_not_print" not in captured.out

    monkeypatch.setenv("CREWAI_DEBUG_LOGS", "true")
    get_settings.cache_clear()
    assert is_debug_logging_enabled() is True
    debug_log("should_print")
    captured = capsys.readouterr()
    assert "should_print" in captured.out
