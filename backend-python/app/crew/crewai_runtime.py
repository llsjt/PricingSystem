"""
CrewAI 运行时辅助模块，负责适配兼容 OpenAI Chat Completions 协议的模型接口。
"""
# CrewAI 运行时工具模块，负责 LLM 构建、调试日志和 JSON 提取等辅助逻辑。


import contextvars
import json
import os
import queue
import re
import threading
import time
from typing import Any

import httpx
from crewai import Agent, Task
from crewai.llms.base_llm import BaseLLM, LLMCallType

from app.core.config import get_settings

# 在本地开发和当前运行环境中默认关闭遥测，避免把调试信息发送到外部服务。
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


def is_debug_logging_enabled() -> bool:
    return bool(get_settings().crewai_debug_logs)


def debug_log(message: str) -> None:
    if is_debug_logging_enabled():
        print(message, flush=True)


class LLMHttpError(RuntimeError):
    def __init__(self, *, status_code: int, body: str, url: str) -> None:
        self.status_code = status_code
        self.body = body
        self.url = url
        super().__init__(f"LLM API HTTP {status_code}, url={url}, body={body[:600]}")


class OpenAICompatibleCrewAILLM(BaseLLM):
    """
    面向 OpenAI 兼容聊天补全接口的 CrewAI 适配器。
    """

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
            raise ValueError("LLM_API_KEY cannot be blank")
        if not normalized_base:
            raise ValueError("LLM_BASE_URL cannot be blank")
        if not model.strip():
            raise ValueError("MODEL cannot be blank")

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

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"0", "false", "no", "off"}

    @staticmethod
    def _coerce_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return min(max(parsed, minimum), maximum)

    @staticmethod
    def _setting_value(settings: Any, attr_name: str, env_name: str, default: Any) -> Any:
        value = getattr(settings, attr_name, None)
        if value is not None:
            return value
        return os.getenv(env_name, default)

    @staticmethod
    def _extract_tool_names(tools: list[dict[str, Any]] | None) -> set[str]:
        names: set[str] = set()
        for tool in tools or []:
            if not isinstance(tool, dict):
                continue
            function_payload = tool.get("function")
            if isinstance(function_payload, dict) and isinstance(function_payload.get("name"), str):
                names.add(function_payload["name"])
            elif isinstance(tool.get("name"), str):
                names.add(tool["name"])
        return names

    @staticmethod
    def _tool_error_payload(error_type: str, error_message: str) -> str:
        return json.dumps(
            {
                "ok": False,
                "data": None,
                "errorType": error_type,
                "errorMessage": error_message,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _truncate_text(value: Any, limit: int = 500) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text if len(text) <= limit else f"{text[: limit - 3]}..."

    @staticmethod
    def _get_active_tool_context() -> Any | None:
        try:
            from app.tools.tool_context import active_tool_context

            return active_tool_context.get()
        except Exception:
            return None

    def _append_tool_audit(self, entry: dict[str, Any]) -> None:
        if not bool(getattr(get_settings(), "crewai_tool_audit_enabled", True)):
            return
        ctx = self._get_active_tool_context()
        logs = getattr(ctx, "tool_audit_logs", None)
        if not isinstance(logs, list):
            return
        if len(logs) >= 20:
            if not any(isinstance(item, dict) and item.get("truncated") for item in logs):
                logs.append(
                    {
                        "status": "skipped",
                        "errorType": "TOOL_AUDIT_TRUNCATED",
                        "errorMessage": "tool audit logs exceeded max retained entries",
                        "truncated": True,
                    }
                )
            return
        logs.append(entry)

    def _build_audit_entry(
        self,
        *,
        tool_call_id: str | None,
        round_index: int,
        from_agent: Agent | None,
        tool_name: str | None,
        status: str,
        elapsed_ms: int,
        args: dict[str, Any] | None = None,
        result: Any = None,
        error_type: str | None = None,
        error_message: str | None = None,
        timeout_warning: bool = False,
    ) -> dict[str, Any]:
        ctx = self._get_active_tool_context()
        return {
            "toolCallId": tool_call_id,
            "roundIndex": round_index + 1,
            "agentCode": getattr(ctx, "agent_code", None) or getattr(from_agent, "role", "unknown"),
            "toolName": tool_name,
            "status": status,
            "elapsedMs": elapsed_ms,
            "argsSummary": args or {},
            "resultSummary": self._truncate_text(result),
            "errorType": error_type,
            "errorMessage": self._truncate_text(error_message),
            "timeoutWarning": timeout_warning,
            "truncated": False,
        }

    @staticmethod
    def _should_degrade_tools(error: LLMHttpError, payload: dict[str, Any]) -> bool:
        if error.status_code not in {400, 422}:
            return False
        if "tools" not in payload and "tool_choice" not in payload:
            return False
        body = (error.body or "").lower()
        has_tool_schema_subject = any(
            token in body for token in ("tools", "tool_choice", "tool_calls", "schema", "unknown field")
        )
        has_unsupported_semantic = any(
            token in body for token in ("unsupported", "unknown field", "schema", "not support", "invalid")
        )
        return has_tool_schema_subject and has_unsupported_semantic

    def _request_chat_completion(
        self,
        *,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> tuple[dict[str, Any], bool]:
        try:
            return self._request_with_retry(payload=payload, headers=headers), False
        except LLMHttpError as original_error:
            if not self._should_degrade_tools(original_error, payload):
                raise

            degraded_payload = dict(payload)
            degraded_payload.pop("tools", None)
            degraded_payload.pop("tool_choice", None)
            debug_log("[LLM] tool_calling_degraded=true reason=tools_schema_unsupported")
            self._append_tool_audit(
                {
                    "toolCallId": None,
                    "roundIndex": None,
                    "agentCode": getattr(self._get_active_tool_context(), "agent_code", "unknown"),
                    "toolName": None,
                    "status": "degraded",
                    "elapsedMs": 0,
                    "argsSummary": {},
                    "resultSummary": None,
                    "errorType": "TOOLS_SCHEMA_UNSUPPORTED",
                    "errorMessage": self._truncate_text(original_error.body),
                    "timeoutWarning": False,
                    "truncated": False,
                }
            )
            try:
                return self._request_with_retry(payload=degraded_payload, headers=headers), True
            except Exception:
                raise original_error

    def _parse_tool_arguments(self, raw_args: Any) -> tuple[dict[str, Any] | None, str | None]:
        if raw_args in (None, ""):
            return {}, None
        if isinstance(raw_args, dict):
            return raw_args, None
        if not isinstance(raw_args, str):
            return None, "tool arguments must be a JSON object"
        try:
            parsed = json.loads(raw_args)
        except json.JSONDecodeError as exc:
            return None, f"tool arguments are not valid JSON: {exc.msg}"
        if not isinstance(parsed, dict):
            return None, "tool arguments JSON must decode to an object"
        return parsed, None

    def _execute_or_reject_tool_call(
        self,
        *,
        tool_call: dict[str, Any],
        tool_index: int,
        round_index: int,
        max_per_round: int,
        allowed_tool_names: set[str],
        available_functions: dict[str, Any],
        tool_timeout_seconds: int,
        from_task: Task | None,
        from_agent: Agent | None,
    ) -> dict[str, str]:
        tool_call_id = tool_call.get("id")
        function_payload = tool_call.get("function")
        function_name = function_payload.get("name") if isinstance(function_payload, dict) else None

        def build_error(
            error_type: str,
            error_message: str,
            args: dict[str, Any] | None = None,
            *,
            status: str = "error",
        ) -> dict[str, str]:
            self._append_tool_audit(
                self._build_audit_entry(
                    tool_call_id=tool_call_id,
                    round_index=round_index,
                    from_agent=from_agent,
                    tool_name=function_name if isinstance(function_name, str) else None,
                    status=status,
                    elapsed_ms=0,
                    args=args,
                    error_type=error_type,
                    error_message=error_message,
                )
            )
            return {
                "role": "tool",
                "tool_call_id": str(tool_call_id),
                "content": self._tool_error_payload(error_type, error_message),
            }

        if tool_index >= max_per_round:
            return build_error(
                "TOOL_RATE_LIMITED",
                "tool call skipped because max_per_round was exceeded",
                status="skipped",
            )

        if not isinstance(function_payload, dict) or not isinstance(function_name, str) or not function_name:
            return build_error("TOOL_MALFORMED", "tool call function payload is malformed")

        parsed_args, args_error = self._parse_tool_arguments(function_payload.get("arguments"))
        if args_error:
            return build_error("TOOL_ARGUMENTS_MALFORMED", args_error)

        if function_name not in allowed_tool_names:
            return build_error("TOOL_UNAUTHORIZED", f"tool is not available for this agent: {function_name}", parsed_args)

        started_at = time.perf_counter()
        result, error_type, error_message = self._run_tool_with_timeout(
            function_name=function_name,
            function_args=parsed_args or {},
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
            timeout_seconds=tool_timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        if error_type is not None:
            return build_error(
                error_type,
                error_message or f"tool execution failed: {function_name}",
                parsed_args,
                status="timeout" if error_type == "TOOL_TIMEOUT" else "error",
            )

        content = result
        self._append_tool_audit(
            self._build_audit_entry(
                tool_call_id=tool_call_id,
                round_index=round_index,
                from_agent=from_agent,
                tool_name=function_name,
                status="success",
                elapsed_ms=elapsed_ms,
                args=parsed_args,
                result=result,
            )
        )
        return {"role": "tool", "tool_call_id": str(tool_call_id), "content": content}

    def _run_tool_with_timeout(
        self,
        *,
        function_name: str,
        function_args: dict[str, Any],
        available_functions: dict[str, Any],
        from_task: Task | None,
        from_agent: Agent | None,
        timeout_seconds: int,
    ) -> tuple[Any | None, str | None, str | None]:
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)
        run_context = contextvars.copy_context()

        def target() -> None:
            try:
                result = run_context.run(
                    self._handle_tool_execution,
                    function_name=function_name,
                    function_args=function_args,
                    available_functions=available_functions,
                    from_task=from_task,
                    from_agent=from_agent,
                )
            except Exception as exc:  # noqa: BLE001
                result_queue.put(("error", str(exc)))
                return
            result_queue.put(("success", result))

        worker = threading.Thread(target=target, daemon=True)
        worker.start()
        worker.join(timeout=max(float(timeout_seconds), 0.001))
        if worker.is_alive():
            return None, "TOOL_TIMEOUT", f"tool execution exceeded {timeout_seconds}s timeout: {function_name}"

        try:
            status, value = result_queue.get_nowait()
        except queue.Empty:
            return None, "TOOL_EXECUTION_ERROR", f"tool execution returned no result: {function_name}"
        if status == "error":
            return None, "TOOL_EXECUTION_ERROR", str(value)
        if value is None:
            return None, "TOOL_EXECUTION_ERROR", f"tool execution failed: {function_name}"
        return value, None, None

    def _request_with_retry(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        last_error: Exception | None = None
        msg_count = len(payload.get("messages", []))
        payload_size = len(json.dumps(payload, ensure_ascii=False))
        debug_log(
            f"[LLM] request model={self.model} messages={msg_count} "
            f"payload={payload_size} timeout={self.timeout_seconds}s read={self.read_timeout_seconds}s"
        )

        for attempt in range(self.max_retries + 1):
            started_at = time.time()
            try:
                with httpx.Client(timeout=self._build_httpx_timeout()) as client:
                    response = client.post(self.chat_completions_url, json=payload, headers=headers)
                elapsed = time.time() - started_at
                debug_log(f"[LLM] response status={response.status_code} elapsed={elapsed:.1f}s")
                response.raise_for_status()
                result = response.json()
                usage = result.get("usage")
                if isinstance(usage, dict):
                    debug_log(f"[LLM] usage={usage}")
                return result
            except httpx.HTTPStatusError as exc:
                elapsed = time.time() - started_at
                last_error = exc
                status_code = exc.response.status_code
                detail = exc.response.text[:600]
                debug_log(f"[LLM] http status={status_code} elapsed={elapsed:.1f}s body={detail}")
                if status_code in retryable_statuses and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise LLMHttpError(
                    status_code=status_code,
                    url=self.chat_completions_url,
                    body=detail,
                ) from exc
            except httpx.TimeoutException as exc:
                elapsed = time.time() - started_at
                last_error = exc
                debug_log(
                    f"[LLM] timeout elapsed={elapsed:.1f}s connect={self.connect_timeout_seconds}s "
                    f"read={self.read_timeout_seconds}s"
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(
                    "LLM API timeout "
                    f"(connect={self.connect_timeout_seconds}s, read={self.read_timeout_seconds}s, "
                    f"total={self.timeout_seconds}s)"
                ) from exc
            except httpx.RequestError as exc:
                elapsed = time.time() - started_at
                last_error = exc
                debug_log(f"[LLM] request-error elapsed={elapsed:.1f}s error={exc}")
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
        agent_name = getattr(from_agent, "role", "unknown") if from_agent else "unknown"
        debug_log(f"[LLM] call start agent={agent_name}")
        history = [dict(message) for message in self._format_messages(messages)]
        debug_log(f"[LLM] formatted-messages={len(history)}")
        if from_agent is None and not self._invoke_before_llm_call_hooks(history, from_agent):
            raise ValueError("LLM call blocked by before_llm_call hook")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        settings = get_settings()
        tools_enabled = self._coerce_bool(
            self._setting_value(settings, "crewai_tool_calling_enabled", "CREWAI_TOOL_CALLING_ENABLED", True),
            True,
        )
        max_rounds = self._coerce_int(
            self._setting_value(settings, "crewai_tool_call_max_rounds", "CREWAI_TOOL_CALL_MAX_ROUNDS", 2),
            2,
            minimum=1,
            maximum=5,
        )
        max_per_round = self._coerce_int(
            self._setting_value(settings, "crewai_tool_call_max_per_round", "CREWAI_TOOL_CALL_MAX_PER_ROUND", 2),
            2,
            minimum=1,
            maximum=5,
        )
        tool_timeout_seconds = self._coerce_int(
            self._setting_value(settings, "crewai_tool_timeout_seconds", "CREWAI_TOOL_TIMEOUT_SECONDS", 5),
            5,
            minimum=1,
            maximum=30,
        )
        available_functions = available_functions or {}
        tool_schema_names = self._extract_tool_names(tools)
        allowed_tool_names = set(available_functions).intersection(tool_schema_names or set(available_functions))
        active_tool_context = self._get_active_tool_context()
        agent_code = getattr(active_tool_context, "agent_code", None)
        if agent_code:
            try:
                from app.tools.tool_registry import allowed_tool_names as registry_allowed_tool_names

                allowed_tool_names &= registry_allowed_tool_names(agent_code)
            except Exception:
                allowed_tool_names = set()
        tools_supported = True

        base_payload: dict[str, Any] = {"model": self.model}
        if self.temperature is not None:
            base_payload["temperature"] = self.temperature
        if self.stop:
            base_payload["stop"] = self.stop

        self._emit_call_started_event(
            messages=history,
            tools=tools,
            callbacks=callbacks,
            available_functions=available_functions,
            from_task=from_task,
            from_agent=from_agent,
        )
        try:
            for round_index in range(max_rounds + 1):
                payload = dict(base_payload)
                payload["messages"] = history
                include_tools = bool(tools_enabled and tools_supported and tools)
                if include_tools:
                    payload["tools"] = tools

                result, degraded = self._request_chat_completion(payload=payload, headers=headers)
                if degraded:
                    tools_supported = False

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
                if content:
                    debug_log(f"[LLM] content-preview={content[:200]}")

                raw_tool_calls = message_payload.get("tool_calls")
                tool_calls = raw_tool_calls if isinstance(raw_tool_calls, list) else []
                if not tool_calls or not tools_enabled or not tools_supported or not tools:
                    if not content:
                        raise RuntimeError("LLM response contained no usable text content")

                    content = self._apply_stop_words(content)
                    if from_agent is None:
                        content = self._invoke_after_llm_call_hooks(history, content, from_agent)
                    final_result: str | Any = (
                        response_model.model_validate_json(content) if response_model is not None else content
                    )
                    self._emit_call_completed_event(
                        response=final_result,
                        call_type=LLMCallType.LLM_CALL,
                        from_task=from_task,
                        from_agent=from_agent,
                        messages=history,
                    )
                    return final_result

                if round_index >= max_rounds:
                    message = "Agent tool calling loop exceeded hard limit."
                    self._append_tool_audit(
                        self._build_audit_entry(
                            tool_call_id=None,
                            round_index=round_index,
                            from_agent=from_agent,
                            tool_name=None,
                            status="error",
                            elapsed_ms=0,
                            error_type="TOOL_LOOP_EXCEEDED",
                            error_message=message,
                        )
                    )
                    raise RuntimeError(message)

                for tool_call in tool_calls:
                    if not isinstance(tool_call, dict) or not tool_call.get("id"):
                        message = "LLM tool_call missing id; cannot close OpenAI tool_calls protocol."
                        self._append_tool_audit(
                            self._build_audit_entry(
                                tool_call_id=None,
                                round_index=round_index,
                                from_agent=from_agent,
                                tool_name=None,
                                status="error",
                                elapsed_ms=0,
                                error_type="TOOL_CALL_ID_MISSING",
                                error_message=message,
                            )
                        )
                        raise RuntimeError(message)

                history.append(
                    {
                        "role": "assistant",
                        "content": message_payload.get("content") or "",
                        "tool_calls": tool_calls,
                    }
                )
                for tool_index, tool_call in enumerate(tool_calls):
                    history.append(
                        self._execute_or_reject_tool_call(
                            tool_call=tool_call,
                            tool_index=tool_index,
                            round_index=round_index,
                            max_per_round=max_per_round,
                            allowed_tool_names=allowed_tool_names,
                            available_functions=available_functions,
                            tool_timeout_seconds=tool_timeout_seconds,
                            from_task=from_task,
                            from_agent=from_agent,
                        )
                    )

            raise RuntimeError("Agent tool calling loop exceeded hard limit.")
        except Exception as exc:
            self._emit_call_failed_event(error=str(exc), from_task=from_task, from_agent=from_agent)
            raise


def build_crewai_llm(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> OpenAICompatibleCrewAILLM:
    settings = get_settings()

    effective_api_key = api_key.strip() if api_key else ""
    effective_base_url = base_url.strip() if base_url else ""
    selected_model = model.strip() if model else ""

    missing: list[str] = []
    if not effective_api_key:
        missing.append("LLM_API_KEY")
    if not effective_base_url:
        missing.append("LLM_BASE_URL")
    if not selected_model:
        missing.append("MODEL")
    if missing:
        raise RuntimeError(f"Missing required LLM config: {', '.join(missing)}")

    session_budget = max(int(settings.crewai_session_timeout_seconds or 0), 10)
    total_timeout = min(max(int(settings.crewai_llm_timeout_seconds or 0), 8), max(session_budget - 5, 8))
    connect_timeout = min(max(int(settings.crewai_llm_connect_timeout_seconds or 0), 2), max(total_timeout - 2, 2))
    read_timeout = min(max(int(settings.crewai_llm_read_timeout_seconds or 0), 5), max(total_timeout - 1, 5))
    max_retries = max(int(settings.crewai_llm_max_retries or 0), 0)

    return OpenAICompatibleCrewAILLM(
        api_key=effective_api_key,
        base_url=effective_base_url,
        model=selected_model,
        timeout_seconds=total_timeout,
        connect_timeout_seconds=connect_timeout,
        read_timeout_seconds=read_timeout,
        max_retries=max_retries,
        retry_backoff_seconds=settings.llm_retry_backoff_seconds,
    )


def _repair_json_text(text: str) -> str:
    """修复 LLM 常见的 JSON 格式错误（双逗号、尾逗号、引号粘连等）。"""
    # 修复双左花括号: {{ → {
    text = re.sub(r"\{\s*\{", "{", text)
    # 修复双逗号: ,, → ,
    text = re.sub(r",\s*,", ",", text)
    # 修复值与下一个键之间的粘连引号: "value","  "key" → "value", "key"
    # 例如 "LOW","  "needManualReview" 中的多余引号
    text = re.sub(r'","\s*"', '", "', text)
    # 修复尾逗号: ,} → }  ,] → ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _repair_truncated_json(text: str) -> str:
    """尝试修复被 max_tokens 截断的 JSON（闭合未关闭的字符串、数组、对象）。

    典型场景：LLM 输出被截断后形如
      { "price": 44.13, "thinking": "分析竞品数据显示...品牌
    需要补全为
      { "price": 44.13, "thinking": "分析竞品数据显示...品牌" }

    修复策略：从末尾向前扫描，依次闭合 string → array → object。
    """
    text = text.rstrip()
    if not text:
        return text

    # 移除末尾不完整的 key（如 , "incompleteKey 或 , "incompleteKey":）
    text = re.sub(r',\s*"[^"]*"\s*:\s*$', '', text)
    text = re.sub(r',\s*"[^"]*$', '', text)

    # 判断是否在未闭合的字符串中：统计未转义的引号数量
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '\\' and in_string:
            i += 2  # 跳过转义字符
            continue
        if ch == '"':
            in_string = not in_string
        i += 1

    # 如果最后仍处于字符串内部，闭合它
    if in_string:
        text += '"'

    # 移除末尾悬空的逗号/冒号
    text = re.sub(r'[,:]\s*$', '', text)

    # 统计未闭合的括号并补全
    open_braces = 0
    open_brackets = 0
    in_str = False
    j = 0
    while j < len(text):
        ch = text[j]
        if ch == '\\' and in_str:
            j += 2
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == '{':
                open_braces += 1
            elif ch == '}':
                open_braces -= 1
            elif ch == '[':
                open_brackets += 1
            elif ch == ']':
                open_brackets -= 1
        j += 1

    text += ']' * max(open_brackets, 0)
    text += '}' * max(open_braces, 0)
    return text


def extract_json_object(raw_output: str) -> dict[str, Any]:
    text = (raw_output or "").strip()
    if not text:
        return {}

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()
    else:
        # 未闭合的 ```json 围栏（输出被 max_tokens 截断，没有 closing ```）
        unclosed = re.match(r"```(?:json)?\s*([\s\S]*)", text, re.IGNORECASE)
        if unclosed:
            text = unclosed.group(1).strip()

    # 尝试直接解析
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 提取 JSON 对象子串（完整的 { ... }）
    object_match = re.search(r"\{[\s\S]*\}", text)
    if object_match:
        candidate = object_match.group(0)
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        # 修复常见 LLM JSON 格式错误后重试
        repaired = _repair_json_text(candidate)
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    # ── 最后手段：修复被 max_tokens 截断的不完整 JSON ──
    # 找到第一个 { 开始的子串（可能没有 } 结尾）
    brace_start = text.find("{")
    if brace_start >= 0:
        fragment = text[brace_start:]
        repaired = _repair_truncated_json(_repair_json_text(fragment))
        try:
            parsed = json.loads(repaired)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    return {}
