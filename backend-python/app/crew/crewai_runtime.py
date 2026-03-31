"""
CrewAI LLM 适配器
=================
实现 OpenAI 兼容的 LLM 调用适配器，供 CrewAI Agent 使用。
支持阿里通义千问（DashScope）、OpenAI 及其他兼容 API。

主要组件：
- OpenAICompatibleCrewAILLM: BaseLLM 子类，处理 HTTP 请求、重试、超时
- build_crewai_llm(): 从配置构建 LLM 实例
- extract_json_object(): 从 LLM 输出中提取 JSON（供卡片解析复用）
"""

import json
import os
import re
import time
from typing import Any

import httpx

# 禁用 CrewAI 遥测，减少本地开发时的网络开销
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Task
from crewai.llms.base_llm import BaseLLM

from app.core.config import get_settings


class OpenAICompatibleCrewAILLM(BaseLLM):
    """
    OpenAI 兼容的 Chat Completions 端点适配器。
    支持 DashScope（通义千问）、OpenAI 及其他兼容 API。
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
        # 参数校验
        normalized_base = (base_url or "").strip().rstrip("/")
        if not api_key.strip():
            raise ValueError("LLM_API_KEY 不能为空")
        if not normalized_base:
            raise ValueError("LLM_BASE_URL 不能为空")
        if not model.strip():
            raise ValueError("MODEL 不能为空")

        super().__init__(
            model=model.strip(),
            provider="openai-compatible",
            api_key=api_key.strip(),
            base_url=normalized_base,
            temperature=temperature,
        )

        # 构建 Chat Completions URL
        self.chat_completions_url = self._build_chat_completions_url(normalized_base)
        # 超时与重试参数
        self.timeout_seconds = max(int(timeout_seconds or 0), 5)
        self.connect_timeout_seconds = max(int(connect_timeout_seconds or 0), 2)
        self.read_timeout_seconds = max(int(read_timeout_seconds or 0), 5)
        self.max_retries = max(int(max_retries or 0), 0)
        self.retry_backoff_seconds = max(float(retry_backoff_seconds or 0), 0.1)

    @staticmethod
    def _build_chat_completions_url(base_url: str) -> str:
        """拼接 /chat/completions 路径"""
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    @staticmethod
    def _normalize_content(content: Any) -> str:
        """将 LLM 响应中的 content 字段统一为纯文本"""
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
        """构建 httpx 超时配置"""
        return httpx.Timeout(
            timeout=float(self.timeout_seconds),
            connect=float(self.connect_timeout_seconds),
            read=float(self.read_timeout_seconds),
        )

    def _request_with_retry(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """
        带重试的 HTTP 请求。
        对 408/429/5xx 状态码自动重试，使用指数退避策略。
        """
        retryable_statuses = {408, 429, 500, 502, 503, 504}
        last_error: Exception | None = None
        msg_count = len(payload.get("messages", []))
        payload_size = len(json.dumps(payload, ensure_ascii=False))
        print(
            f"[LLM] 发送请求: url={self.chat_completions_url}, model={self.model}, "
            f"消息数={msg_count}, payload大小={payload_size}字符, "
            f"timeout={self.timeout_seconds}s, read_timeout={self.read_timeout_seconds}s",
            flush=True,
        )

        for attempt in range(self.max_retries + 1):
            t0 = time.time()
            try:
                with httpx.Client(timeout=self._build_httpx_timeout()) as client:
                    resp = client.post(self.chat_completions_url, json=payload, headers=headers)
                elapsed = time.time() - t0
                print(f"[LLM] 响应: status={resp.status_code}, 耗时={elapsed:.1f}s", flush=True)
                resp.raise_for_status()
                result = resp.json()
                # 打印 token 用量
                usage = result.get("usage")
                if isinstance(usage, dict):
                    print(f"[LLM] Token用量: {usage}", flush=True)
                return result
            except httpx.HTTPStatusError as exc:
                elapsed = time.time() - t0
                last_error = exc
                status_code = exc.response.status_code
                detail = exc.response.text[:600]
                print(f"[LLM] HTTP错误: status={status_code}, 耗时={elapsed:.1f}s, body={detail}", flush=True)
                if status_code in retryable_statuses and attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(
                    f"LLM API HTTP {status_code}, url={self.chat_completions_url}, body={detail}"
                ) from exc
            except httpx.TimeoutException as exc:
                elapsed = time.time() - t0
                last_error = exc
                print(
                    f"[LLM] 超时: 耗时={elapsed:.1f}s, "
                    f"connect={self.connect_timeout_seconds}s, read={self.read_timeout_seconds}s",
                    flush=True,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(
                    "LLM API 超时 "
                    f"(connect={self.connect_timeout_seconds}s, "
                    f"read={self.read_timeout_seconds}s, total={self.timeout_seconds}s)"
                ) from exc
            except httpx.RequestError as exc:
                elapsed = time.time() - t0
                last_error = exc
                print(f"[LLM] 请求错误: {exc}, 耗时={elapsed:.1f}s", flush=True)
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2**attempt))
                    continue
                raise RuntimeError(f"LLM API 请求失败: {exc}") from exc
            except ValueError as exc:
                raise RuntimeError(f"LLM API 返回非JSON响应: {exc}") from exc

        raise RuntimeError(f"LLM API 请求在重试后仍失败: {last_error}")

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
        """
        调用 LLM Chat Completions API。
        这是 CrewAI BaseLLM 要求实现的核心方法。
        """
        # 格式化消息列表
        agent_name = getattr(from_agent, "role", "未知") if from_agent else "无Agent"
        print(f"[LLM] call() 开始: agent={agent_name}", flush=True)
        request_messages = self._format_messages(messages)
        print(f"[LLM] 消息格式化完成: {len(request_messages)}条消息", flush=True)
        if from_agent is None and not self._invoke_before_llm_call_hooks(request_messages, from_agent):
            raise ValueError("LLM 调用被 before_llm_call hook 阻止")

        # 构建请求体
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

        # 发送请求（带重试）
        result = self._request_with_retry(payload=payload, headers=headers)

        # 记录 token 使用量
        usage = result.get("usage")
        if isinstance(usage, dict):
            self._track_token_usage_internal(usage)

        # 解析响应
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LLM 响应缺少 choices 字段")

        message_payload = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message_payload, dict):
            raise RuntimeError("LLM 响应缺少 message 字段")

        # 提取文本内容
        content = self._normalize_content(message_payload.get("content"))

        if content:
            print(f"[LLM] 文本响应前200字符: {content[:200]}", flush=True)

        # 如果没有文本内容，尝试处理 tool_calls（function calling）
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
                            print(f"[LLM] 处理tool_call: {function_name}, args={str(parsed_args)[:200]}", flush=True)
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
            raise RuntimeError("LLM 响应未包含文本内容")

        # 应用停用词过滤
        content = self._apply_stop_words(content)
        if from_agent is None:
            content = self._invoke_after_llm_call_hooks(request_messages, content, from_agent)
        return content


def build_crewai_llm() -> OpenAICompatibleCrewAILLM:
    """
    从应用配置构建 CrewAI LLM 实例。
    读取 .env 中的 LLM_API_KEY、LLM_BASE_URL、MODEL 等配置。
    """
    settings = get_settings()

    # 校验必需的 LLM 配置项
    missing: list[str] = []
    if not settings.llm_api_key.strip():
        missing.append("LLM_API_KEY")
    if not settings.llm_base_url.strip():
        missing.append("LLM_BASE_URL")
    if not settings.llm_model.strip():
        missing.append("MODEL")
    if missing:
        raise RuntimeError(f"缺少必需的 LLM 配置: {', '.join(missing)}")

    # 计算超时参数，确保单次调用不超过 CrewAI 会话预算
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


def extract_json_object(raw_output: str) -> dict[str, Any]:
    """
    从 LLM 原始输出文本中提取 JSON 对象。
    支持从 Markdown 代码块、纯 JSON 文本或混合文本中提取。
    用于解析 Agent 输出并构建前端展示的卡片数据。
    """
    text = (raw_output or "").strip()
    if not text:
        return {}

    # 尝试从 Markdown 代码块中提取 JSON
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    # 尝试直接解析为 JSON
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # 兜底：提取文本中最后一个 JSON 对象（LLM 可能在 JSON 前后附加说明文字）
    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        try:
            parsed = json.loads(obj_match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}
