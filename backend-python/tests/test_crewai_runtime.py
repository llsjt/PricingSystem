from inspect import signature

import pytest

from app.agents import crewai_agents
from app.core.config import Settings, get_settings
from app.crew.crewai_runtime import build_crewai_llm, debug_log, is_debug_logging_enabled


def _set_minimal_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.com/v1")


def test_build_crewai_llm_requires_explicit_model_even_if_model_env_exists(monkeypatch):
    _set_minimal_llm_env(monkeypatch)
    monkeypatch.setenv("MODEL", "default-model")
    get_settings.cache_clear()

    assert "profile" not in signature(build_crewai_llm).parameters

    with pytest.raises(RuntimeError, match="MODEL"):
        build_crewai_llm()


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


def test_default_analysis_llm_budget_keeps_frontend_responsive(monkeypatch):
    for key in (
        "CREWAI_LLM_TIMEOUT_SECONDS",
        "CREWAI_LLM_READ_TIMEOUT_SECONDS",
        "CREWAI_LLM_MAX_RETRIES",
        "ANALYSIS_AGENT_MAX_EXEC_SECONDS",
        "FAST_AGENT_MAX_EXEC_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings(_env_file=None)

    assert settings.crewai_llm_timeout_seconds <= 60
    assert settings.crewai_llm_read_timeout_seconds <= 45
    assert settings.crewai_llm_max_retries == 0
    assert settings.analysis_agent_max_execution_seconds <= 75


def test_tool_loop_agents_are_kept_one_shot(monkeypatch):
    class _FakeAgent:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.role = kwargs["role"]
            self.tools = kwargs["tools"]

    monkeypatch.setattr(crewai_agents, "Agent", _FakeAgent)

    agents = crewai_agents.build_crewai_agents(analysis_llm=object(), manager_llm=object())

    assert agents["DATA_ANALYSIS"].tools == []
    assert agents["MARKET_INTEL"].tools == []
    assert agents["RISK_CONTROL"].tools == []
    assert agents["MANAGER_COORDINATOR"].tools


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
