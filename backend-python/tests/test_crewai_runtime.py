from inspect import signature

from app.core.config import get_settings
from app.crew.crewai_runtime import build_crewai_llm, debug_log, is_debug_logging_enabled


def _set_minimal_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("MODEL", "default-model")


def test_build_crewai_llm_exposes_no_profile_split(monkeypatch):
    _set_minimal_llm_env(monkeypatch)
    get_settings.cache_clear()

    assert "profile" not in signature(build_crewai_llm).parameters

    llm = build_crewai_llm()

    assert llm.model == "default-model"


def test_analysis_agent_settings_prefer_new_env_names(monkeypatch):
    monkeypatch.setenv("ANALYSIS_AGENT_MAX_ITER", "7")
    monkeypatch.setenv("FAST_AGENT_MAX_ITER", "3")
    monkeypatch.setenv("ANALYSIS_AGENT_MAX_EXEC_SECONDS", "420")
    monkeypatch.setenv("FAST_AGENT_MAX_EXEC_SECONDS", "120")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.analysis_agent_max_iter == 7
    assert settings.analysis_agent_max_execution_seconds == 420


def test_analysis_agent_settings_keep_legacy_fast_env_fallback(monkeypatch):
    monkeypatch.delenv("ANALYSIS_AGENT_MAX_ITER", raising=False)
    monkeypatch.delenv("ANALYSIS_AGENT_MAX_EXEC_SECONDS", raising=False)
    monkeypatch.setenv("FAST_AGENT_MAX_ITER", "5")
    monkeypatch.setenv("FAST_AGENT_MAX_EXEC_SECONDS", "240")
    get_settings.cache_clear()

    settings = get_settings()

    assert settings.analysis_agent_max_iter == 5
    assert settings.analysis_agent_max_execution_seconds == 240


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
