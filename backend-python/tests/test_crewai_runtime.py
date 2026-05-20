import contextvars
import json
from types import SimpleNamespace
from inspect import signature

import pytest
from pydantic import BaseModel

from app.agents import crewai_agents
from app.core.config import Settings, get_settings
from app.crew import crewai_runtime
from app.crew.crewai_runtime import OpenAICompatibleCrewAILLM, build_crewai_llm, debug_log, is_debug_logging_enabled


def _make_llm(monkeypatch, responses):
    llm = OpenAICompatibleCrewAILLM(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        timeout_seconds=5,
        connect_timeout_seconds=2,
        read_timeout_seconds=5,
        max_retries=0,
        retry_backoff_seconds=0.1,
    )
    captured_payloads = []
    queued = list(responses)

    def fake_request(payload, headers):  # noqa: ANN001
        captured_payloads.append(json.loads(json.dumps(payload)))
        next_response = queued.pop(0)
        if isinstance(next_response, BaseException):
            raise next_response
        return next_response

    monkeypatch.setattr(llm, "_request_with_retry", fake_request)
    return llm, captured_payloads


def _chat_response(message, usage=None):  # noqa: ANN001
    return {
        "choices": [{"message": message}],
        "usage": usage or {"prompt_tokens": 1, "completion_tokens": 1},
    }


def _tool_call(call_id="call_1", name="lookup_price", arguments=None):  # noqa: ANN001
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": "{}" if arguments is None else arguments,
        },
    }


def _tool_schema(name="lookup_price"):  # noqa: ANN001
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "test tool",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _set_tool_loop_env(monkeypatch, *, max_rounds=2, max_per_round=2, enabled=True):
    monkeypatch.setenv("CREWAI_TOOL_CALLING_ENABLED", "true" if enabled else "false")
    monkeypatch.setenv("CREWAI_TOOL_CALL_MAX_ROUNDS", str(max_rounds))
    monkeypatch.setenv("CREWAI_TOOL_CALL_MAX_PER_ROUND", str(max_per_round))
    monkeypatch.setenv("CREWAI_TOOL_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("CREWAI_TOOL_AUDIT_ENABLED", "true")
    get_settings.cache_clear()


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


def test_react_loop_executes_tool_and_returns_final_content(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "", "tool_calls": [_tool_call(arguments='{"price": 19.9}')]}),
            _chat_response({"content": "final answer"}),
        ],
    )

    result = llm.call(
        "price check",
        tools=[_tool_schema()],
        available_functions={"lookup_price": lambda price: f"price={price}"},
    )

    assert result == "final answer"
    assert len(payloads) == 2
    assert payloads[0]["tools"] == [_tool_schema()]
    second_messages = payloads[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-2]["tool_calls"][0]["id"] == "call_1"
    assert second_messages[-1] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "price=19.9",
    }


def test_content_and_tool_calls_still_enters_tool_loop(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "I should verify this.", "tool_calls": [_tool_call()]}),
            _chat_response({"content": "verified final"}),
        ],
    )

    result = llm.call("verify", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert result == "verified final"
    assert len(payloads) == 2
    assert payloads[1]["messages"][-2]["content"] == "I should verify this."
    assert payloads[1]["messages"][-1]["tool_call_id"] == "call_1"


def test_max_per_round_adds_rate_limited_tool_responses(monkeypatch):
    _set_tool_loop_env(monkeypatch, max_per_round=1)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response(
                {
                    "content": "",
                    "tool_calls": [
                        _tool_call(call_id="call_1"),
                        _tool_call(call_id="call_2"),
                    ],
                }
            ),
            _chat_response({"content": "done"}),
        ],
    )

    result = llm.call("rate limit", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert result == "done"
    tool_messages = [msg for msg in payloads[1]["messages"] if msg["role"] == "tool"]
    assert [msg["tool_call_id"] for msg in tool_messages] == ["call_1", "call_2"]
    skipped_payload = json.loads(tool_messages[1]["content"])
    assert skipped_payload["ok"] is False
    assert skipped_payload["errorType"] == "TOOL_RATE_LIMITED"


def test_malformed_tool_arguments_returns_tool_error(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "", "tool_calls": [_tool_call(arguments="{bad-json")]}),
            _chat_response({"content": "done"}),
        ],
    )

    llm.call("bad args", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "should-not-run"})

    tool_message = payloads[1]["messages"][-1]
    error_payload = json.loads(tool_message["content"])
    assert tool_message["tool_call_id"] == "call_1"
    assert error_payload["ok"] is False
    assert error_payload["errorType"] == "TOOL_ARGUMENTS_MALFORMED"


def test_tool_execution_timeout_returns_structured_tool_error(monkeypatch):
    llm, _ = _make_llm(monkeypatch, [])

    def slow_execution(**kwargs):  # noqa: ANN001, ARG001
        import time

        time.sleep(0.05)
        return "late"

    monkeypatch.setattr(llm, "_handle_tool_execution", slow_execution)

    message = llm._execute_or_reject_tool_call(
        tool_call=_tool_call(arguments="{}"),
        tool_index=0,
        round_index=0,
        max_per_round=2,
        allowed_tool_names={"lookup_price"},
        available_functions={"lookup_price": lambda: "ok"},
        tool_timeout_seconds=0,
        from_task=None,
        from_agent=None,
    )

    error_payload = json.loads(message["content"])
    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_1"
    assert error_payload["ok"] is False
    assert error_payload["errorType"] == "TOOL_TIMEOUT"


def test_tool_audit_enabled_records_success(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    audit_context = SimpleNamespace(tool_audit_logs=[], agent_code=None)
    active_context = contextvars.ContextVar("active_tool_context", default=None)
    active_context.set(audit_context)
    monkeypatch.setitem(
        __import__("sys").modules,
        "app.tools.tool_context",
        SimpleNamespace(active_tool_context=active_context),
    )
    llm, _ = _make_llm(monkeypatch, [])

    message = llm._execute_or_reject_tool_call(
        tool_call=_tool_call(arguments="{}"),
        tool_index=0,
        round_index=0,
        max_per_round=2,
        allowed_tool_names={"lookup_price"},
        available_functions={"lookup_price": lambda: "ok"},
        tool_timeout_seconds=5,
        from_task=None,
        from_agent=None,
    )

    assert message["content"] == "ok"
    assert audit_context.tool_audit_logs[0]["toolName"] == "lookup_price"
    assert audit_context.tool_audit_logs[0]["status"] == "success"


def test_unknown_or_unauthorized_tool_returns_tool_error_and_audit(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    audit_context = SimpleNamespace(tool_audit_logs=[], agent_code="DATA_ANALYSIS")
    active_context = contextvars.ContextVar("active_tool_context", default=None)
    active_context.set(audit_context)
    monkeypatch.setitem(
        __import__("sys").modules,
        "app.tools.tool_context",
        SimpleNamespace(active_tool_context=active_context),
    )
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "", "tool_calls": [_tool_call(name="forbidden_tool")]}),
            _chat_response({"content": "done"}),
        ],
    )

    llm.call("unknown", tools=[_tool_schema("forbidden_tool")], available_functions={"lookup_price": lambda: "ok"})

    error_payload = json.loads(payloads[1]["messages"][-1]["content"])
    assert error_payload["ok"] is False
    assert error_payload["errorType"] == "TOOL_UNAUTHORIZED"
    assert audit_context.tool_audit_logs[0]["toolName"] == "forbidden_tool"
    assert audit_context.tool_audit_logs[0]["status"] == "error"


def test_registered_tool_from_wrong_agent_is_unauthorized(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    audit_context = SimpleNamespace(tool_audit_logs=[], agent_code="DATA_ANALYSIS")
    active_context = contextvars.ContextVar("active_tool_context", default=None)
    active_context.set(audit_context)
    monkeypatch.setitem(
        __import__("sys").modules,
        "app.tools.tool_context",
        SimpleNamespace(active_tool_context=active_context),
    )
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "", "tool_calls": [_tool_call(name="query_competitor_summary")]}),
            _chat_response({"content": "done"}),
        ],
    )

    llm.call(
        "wrong agent",
        tools=[_tool_schema("query_competitor_summary")],
        available_functions={"query_competitor_summary": lambda: "should-not-run"},
    )

    error_payload = json.loads(payloads[1]["messages"][-1]["content"])
    assert error_payload["ok"] is False
    assert error_payload["errorType"] == "TOOL_UNAUTHORIZED"


def test_tool_audit_disabled_still_executes_tool_without_audit(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    monkeypatch.setenv("CREWAI_TOOL_AUDIT_ENABLED", "false")
    get_settings.cache_clear()
    audit_context = SimpleNamespace(tool_audit_logs=[], agent_code=None)
    active_context = contextvars.ContextVar("active_tool_context", default=None)
    active_context.set(audit_context)
    monkeypatch.setitem(
        __import__("sys").modules,
        "app.tools.tool_context",
        SimpleNamespace(active_tool_context=active_context),
    )
    llm, _ = _make_llm(monkeypatch, [])

    message = llm._execute_or_reject_tool_call(
        tool_call=_tool_call(arguments="{}"),
        tool_index=0,
        round_index=0,
        max_per_round=2,
        allowed_tool_names={"lookup_price"},
        available_functions={"lookup_price": lambda: "ok"},
        tool_timeout_seconds=5,
        from_task=None,
        from_agent=None,
    )

    assert message["content"] == "ok"
    assert audit_context.tool_audit_logs == []


def test_tool_audit_disabled_does_not_record_schema_degradation(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    monkeypatch.setenv("CREWAI_TOOL_AUDIT_ENABLED", "false")
    get_settings.cache_clear()
    audit_context = SimpleNamespace(tool_audit_logs=[], agent_code=None)
    active_context = contextvars.ContextVar("active_tool_context", default=None)
    active_context.set(audit_context)
    monkeypatch.setitem(
        __import__("sys").modules,
        "app.tools.tool_context",
        SimpleNamespace(active_tool_context=active_context),
    )
    llm, payloads = _make_llm(
        monkeypatch,
        [
            crewai_runtime.LLMHttpError(
                status_code=400,
                body="unknown field: tools schema is unsupported",
                url="https://example.com/v1/chat/completions",
            ),
            _chat_response({"content": "fallback"}),
        ],
    )

    result = llm.call("fallback", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert result == "fallback"
    assert "tools" in payloads[0]
    assert "tools" not in payloads[1]
    assert audit_context.tool_audit_logs == []


def test_tools_unsupported_400_degrades_once_without_tools(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            crewai_runtime.LLMHttpError(
                status_code=400,
                body="unknown field: tools schema is unsupported",
                url="https://example.com/v1/chat/completions",
            ),
            _chat_response({"content": "one shot fallback"}),
        ],
    )

    result = llm.call("fallback", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert result == "one shot fallback"
    assert "tools" in payloads[0]
    assert "tools" not in payloads[1]
    assert len(payloads) == 2


def test_tools_unsupported_422_degrades_once_without_tools(monkeypatch):
    _set_tool_loop_env(monkeypatch)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            crewai_runtime.LLMHttpError(
                status_code=422,
                body="tool_choice is unsupported by this schema",
                url="https://example.com/v1/chat/completions",
            ),
            _chat_response({"content": "fallback 422"}),
        ],
    )

    result = llm.call("fallback", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert result == "fallback 422"
    assert "tools" not in payloads[1]


def test_tool_loop_exceeded_raises_runtime_error(monkeypatch):
    _set_tool_loop_env(monkeypatch, max_rounds=1)
    llm, payloads = _make_llm(
        monkeypatch,
        [
            _chat_response({"content": "", "tool_calls": [_tool_call(call_id="call_1")]}),
            _chat_response({"content": "", "tool_calls": [_tool_call(call_id="call_2")]}),
        ],
    )

    with pytest.raises(RuntimeError, match="tool calling loop exceeded"):
        llm.call("loop", tools=[_tool_schema()], available_functions={"lookup_price": lambda: "ok"})

    assert len(payloads) == 2
    assert payloads[1]["messages"][-1]["tool_call_id"] == "call_1"


def test_response_model_behavior_is_preserved(monkeypatch):
    class PriceAnswer(BaseModel):
        suggestedPrice: float

    _set_tool_loop_env(monkeypatch)
    llm, _payloads = _make_llm(monkeypatch, [_chat_response({"content": '{"suggestedPrice": 29.9}'})])

    result = llm.call("json", response_model=PriceAnswer)

    assert isinstance(result, PriceAnswer)
    assert result.suggestedPrice == 29.9


def test_agents_receive_role_scoped_tools(monkeypatch):
    class _FakeAgent:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.role = kwargs["role"]
            self.tools = kwargs["tools"]

    monkeypatch.setattr(crewai_agents, "Agent", _FakeAgent)

    agents = crewai_agents.build_crewai_agents(analysis_llm=object(), manager_llm=object())

    assert [tool.name for tool in agents["DATA_ANALYSIS"].tools] == [
        "summarize_product_data",
        "estimate_sales_volume",
        "estimate_profit",
    ]
    assert [tool.name for tool in agents["MARKET_INTEL"].tools] == ["query_competitor_summary"]
    assert [tool.name for tool in agents["RISK_CONTROL"].tools] == ["evaluate_risk_rules"]
    assert [tool.name for tool in agents["MANAGER_COORDINATOR"].tools] == [
        "estimate_sales_volume",
        "estimate_profit",
    ]


def test_agent_builder_uses_tool_registry(monkeypatch):
    class _FakeAgent:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.role = kwargs["role"]
            self.tools = kwargs["tools"]

    sentinel_tool = SimpleNamespace(name="sentinel_tool")

    monkeypatch.setattr(crewai_agents, "Agent", _FakeAgent)
    monkeypatch.setattr(crewai_agents, "get_tools_for_agent", lambda agent_code: [sentinel_tool])

    agents = crewai_agents.build_crewai_agents(analysis_llm=object(), manager_llm=object())

    assert agents["DATA_ANALYSIS"].tools == [sentinel_tool]
    assert agents["MARKET_INTEL"].tools == [sentinel_tool]
    assert agents["RISK_CONTROL"].tools == [sentinel_tool]
    assert agents["MANAGER_COORDINATOR"].tools == [sentinel_tool]


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
