import json
import os
import re
import time
from typing import Any

import httpx

# Disable telemetry to reduce startup/remote-side overhead in local demos.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM

from app.core.config import get_settings
from app.crew.protocols import CrewRunPayload


class OpenAICompatibleCrewAILLM(BaseLLM):
    """Call OpenAI-compatible chat completions endpoint for CrewAI."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int,
        connect_timeout_seconds: int,
        read_timeout_seconds: int,
        max_retries: int,
        retry_backoff_seconds: float,
        temperature: float = 0.2,
    ) -> None:
        normalized_base = (base_url or "").strip().rstrip("/")
        if not api_key.strip():
            raise ValueError("LLM_API_KEY is required")
        if not normalized_base:
            raise ValueError("LLM_BASE_URL is required")
        if not model.strip():
            raise ValueError("MODEL is required")

        super().__init__(
            model=model.strip(),
            provider="openai-compatible",
            api_key=api_key.strip(),
            base_url=normalized_base,
            temperature=temperature,
        )

        self.chat_completions_url = self._build_chat_completions_url(normalized_base)
        self.timeout_seconds = max(int(timeout_seconds or 0), 5)
        self.connect_timeout_seconds = max(int(connect_timeout_seconds or 0), 2)
        self.read_timeout_seconds = max(int(read_timeout_seconds or 0), 5)
        self.max_retries = max(int(max_retries or 0), 0)
        self.retry_backoff_seconds = max(float(retry_backoff_seconds or 0), 0.1)

    @staticmethod
    def _build_chat_completions_url(base_url: str) -> str:
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    @staticmethod
    def _normalize_content(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        chunks.append(text.strip())
                elif isinstance(item, str) and item.strip():
                    chunks.append(item.strip())
            return "\n".join(chunks)
        return ""

    def _build_httpx_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            timeout=float(self.timeout_seconds),
            connect=float(self.connect_timeout_seconds),
            read=float(self.read_timeout_seconds),
        )

    def _request_with_retry(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self._build_httpx_timeout()) as client:
                    resp = client.post(self.chat_completions_url, json=payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in retryable_statuses and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                detail = exc.response.text[:600]
                raise RuntimeError(
                    f"LLM API HTTP {status_code}, url={self.chat_completions_url}, body={detail}"
                ) from exc
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(
                    "LLM API timeout "
                    f"(connect={self.connect_timeout_seconds}s, read={self.read_timeout_seconds}s, total={self.timeout_seconds}s)"
                ) from exc
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(f"LLM API request failed: {exc}") from exc
            except ValueError as exc:
                raise RuntimeError(f"LLM API returned non-JSON response: {exc}") from exc

        raise RuntimeError(f"LLM API request failed after retries: {last_error}")

    def call(
        self,
        messages: str | list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Task | None = None,
        from_agent: Agent | None = None,
        response_model: type | None = None,
    ) -> str | Any:
        request_messages = self._format_messages(messages)
        if from_agent is None and not self._invoke_before_llm_call_hooks(request_messages, from_agent):
            raise ValueError("LLM call blocked by before_llm_call hook")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": request_messages,
        }
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        if self.stop:
            payload["stop"] = self.stop
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        result = self._request_with_retry(payload=payload, headers=headers)

        usage = result.get("usage")
        if isinstance(usage, dict):
            self._track_token_usage_internal(usage)

        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM response missing choices")

        message_payload = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message_payload, dict):
            raise RuntimeError("LLM response missing message")

        content = self._normalize_content(message_payload.get("content"))
        if not content:
            tool_calls = message_payload.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls and available_functions:
                first_tool = tool_calls[0]
                if isinstance(first_tool, dict):
                    function_payload = first_tool.get("function")
                    if isinstance(function_payload, dict):
                        function_name = function_payload.get("name")
                        raw_args = function_payload.get("arguments") or "{}"
                        parsed_args: dict[str, Any] = {}
                        if isinstance(raw_args, str):
                            try:
                                parsed = json.loads(raw_args)
                                if isinstance(parsed, dict):
                                    parsed_args = parsed
                            except json.JSONDecodeError:
                                parsed_args = {}
                        elif isinstance(raw_args, dict):
                            parsed_args = raw_args

                        if isinstance(function_name, str) and function_name:
                            maybe_output = self._handle_tool_execution(
                                function_name=function_name,
                                function_args=parsed_args,
                                available_functions=available_functions,
                                from_task=from_task,
                                from_agent=from_agent,
                            )
                            if isinstance(maybe_output, str) and maybe_output.strip():
                                content = maybe_output

        if not content:
            raise RuntimeError("LLM response did not contain text content")

        content = self._apply_stop_words(content)
        if from_agent is None:
            content = self._invoke_after_llm_call_hooks(request_messages, content, from_agent)
        return content


def build_crewai_llm() -> OpenAICompatibleCrewAILLM:
    settings = get_settings()
    missing: list[str] = []
    if not settings.llm_api_key.strip():
        missing.append("LLM_API_KEY")
    if not settings.llm_base_url.strip():
        missing.append("LLM_BASE_URL")
    if not settings.llm_model.strip():
        missing.append("MODEL")
    if missing:
        raise RuntimeError(f"Missing required LLM config: {', '.join(missing)}")

    # Constrain per-call timeout under CrewAI session budget to avoid long blocking.
    session_budget = max(int(settings.crewai_session_timeout_seconds or 0), 10)
    total_timeout = min(max(int(settings.crewai_llm_timeout_seconds or 0), 8), max(session_budget - 5, 8))
    connect_timeout = min(max(int(settings.crewai_llm_connect_timeout_seconds or 0), 2), max(total_timeout - 2, 2))
    read_timeout = min(max(int(settings.crewai_llm_read_timeout_seconds or 0), 5), max(total_timeout - 1, 5))
    max_retries = max(int(settings.crewai_llm_max_retries or 0), 0)

    return OpenAICompatibleCrewAILLM(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=total_timeout,
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
        max_retries=max_retries,
        retry_backoff_seconds=settings.llm_retry_backoff_seconds,
    )


def _extract_json_object(raw_output: str) -> dict[str, Any]:
    text = (raw_output or "").strip()
    if not text:
        return {}

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _normalize_decision_payload(parsed: dict[str, Any]) -> dict[str, Any]:
    source = parsed
    nested = parsed.get("decision")
    if isinstance(nested, dict):
        source = nested

    def pick_number(*keys: str) -> float | None:
        for key in keys:
            value = source.get(key)
            try:
                if value is not None:
                    return float(value)
            except Exception:
                continue
        return None

    def pick_text(*keys: str) -> str | None:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    return {
        "recommendedPrice": pick_number("recommendedPrice", "consensusPrice"),
        "recommendedMinPrice": pick_number("recommendedMinPrice", "consensusMinPrice"),
        "recommendedMaxPrice": pick_number("recommendedMaxPrice", "consensusMaxPrice"),
        "executeStrategy": pick_text("executeStrategy", "strategy"),
        "reason": pick_text("reason", "riskNote", "decisionReason"),
        "confidence": pick_number("confidence"),
    }


def run_crewai_session(payload: CrewRunPayload, decision_inputs: dict[str, Any]) -> dict[str, Any]:
    """Start a lightweight MVP CrewAI collaboration and return normalized JSON decision."""
    llm = build_crewai_llm()
    settings = get_settings()

    max_iter = max(min(settings.crewai_agent_max_iter, 3), 1)
    max_execution_time = max(min(settings.crewai_agent_max_execution_seconds, 25), 8)
    max_execution_time = min(max_execution_time, max(settings.crewai_session_timeout_seconds - 8, 8))
    max_retry_limit = max(min(settings.crewai_agent_max_retry_limit, 1), 0)

    common_agent_kwargs = {
        "llm": llm,
        "verbose": False,
        "max_iter": max_iter,
        "max_execution_time": max_execution_time,
        "max_retry_limit": max_retry_limit,
    }

    analysis_agent = Agent(
        role="Collab Analyst",
        goal="Find pricing conflicts and feasible range from structured inputs quickly.",
        backstory="Skilled in concise consistency analysis with limited context.",
        allow_delegation=False,
        **common_agent_kwargs,
    )
    manager_agent = Agent(
        role="Decision Manager",
        goal="Produce final executable pricing decision in strict JSON.",
        backstory="Responsible for coordination and decision convergence.",
        allow_delegation=True,
        **common_agent_kwargs,
    )

    compact_inputs = json.dumps(decision_inputs, ensure_ascii=False, separators=(",", ":"))
    analysis_task = Task(
        description=(
            "Read INPUT_JSON and output strict JSON only.\n"
            "Required fields: consensusPrice, consensusMinPrice, consensusMaxPrice, riskNote, confidence.\n"
            f"INPUT_JSON={compact_inputs}"
        ),
        expected_output='{"consensusPrice":0,"consensusMinPrice":0,"consensusMaxPrice":0,"riskNote":"","confidence":0}',
        agent=analysis_agent,
    )
    manager_task = Task(
        description=(
            "Based on previous result, output final decision in strict JSON only.\n"
            "Required fields: recommendedPrice, recommendedMinPrice, recommendedMaxPrice, "
            "executeStrategy(DIRECT_EXECUTE|GRAY_RELEASE|MANUAL_REVIEW), reason, confidence."
        ),
        expected_output=(
            '{"recommendedPrice":0,"recommendedMinPrice":0,"recommendedMaxPrice":0,'
            '"executeStrategy":"GRAY_RELEASE","reason":"","confidence":0}'
        ),
        agent=manager_agent,
        context=[analysis_task],
    )

    crew = Crew(
        name="pricing-mvp-crewai-crew",
        agents=[analysis_agent],
        manager_agent=manager_agent,
        tasks=[analysis_task, manager_task],
        process=Process.hierarchical,
        verbose=False,
    )

    kickoff_start = time.perf_counter()
    output = crew.kickoff(
        inputs={
            "task_id": payload.task_id,
            "product_id": payload.product.product_id,
            "strategy_goal": payload.strategy_goal,
        }
    )
    elapsed_ms = int((time.perf_counter() - kickoff_start) * 1000)

    raw_output = str(output)
    parsed = _extract_json_object(raw_output)
    normalized_decision = _normalize_decision_payload(parsed)

    return {
        "enabled": True,
        "mode": "MVP",
        "process": "hierarchical",
        "taskCount": 2,
        "llmModel": llm.model,
        "llmBaseUrl": llm.base_url,
        "elapsedMs": elapsed_ms,
        "inputChars": len(compact_inputs),
        "tuning": {
            "maxIter": max_iter,
            "maxExecutionSeconds": max_execution_time,
            "maxRetryLimit": max_retry_limit,
        },
        "agentRoles": [analysis_agent.role, manager_agent.role],
        "decision": normalized_decision,
        "crewOutput": raw_output[:1200],
    }
