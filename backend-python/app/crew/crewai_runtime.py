"""
CrewAI 运行时辅助模块，负责适配兼容 OpenAI Chat Completions 协议的模型接口。
"""
# CrewAI 运行时工具模块，负责 LLM 构建、调试日志和 JSON 提取等辅助逻辑。


import json
import os
import re
import time
from typing import Any

import httpx
from crewai import Agent, Task
from crewai.llms.base_llm import BaseLLM

from app.core.config import get_settings

# 在本地开发和当前运行环境中默认关闭遥测，避免把调试信息发送到外部服务。
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")


def is_debug_logging_enabled() -> bool:
    return bool(get_settings().crewai_debug_logs)


def debug_log(message: str) -> None:
    if is_debug_logging_enabled():
        print(message, flush=True)


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
                raise RuntimeError(
                    f"LLM API HTTP {status_code}, url={self.chat_completions_url}, body={detail}"
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
        request_messages = self._format_messages(messages)
        debug_log(f"[LLM] formatted-messages={len(request_messages)}")
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
        if content:
            debug_log(f"[LLM] content-preview={content[:200]}")

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
                            debug_log(f"[LLM] tool-call name={function_name} args={str(parsed_args)[:200]}")
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
            raise RuntimeError("LLM response contained no usable text content")

        content = self._apply_stop_words(content)
        if from_agent is None:
            content = self._invoke_after_llm_call_hooks(request_messages, content, from_agent)
        return content


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
