import json
import os
from typing import Any

import httpx

# 禁用 CrewAI 远端遥测，避免本地离线演示时出现 30s+ 超时。
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM

from app.core.config import get_settings
from app.crew.protocols import CrewRunPayload
from app.utils.math_utils import money


class OpenAICompatibleCrewAILLM(BaseLLM):
    """通过 OpenAI 兼容接口真实调用大模型。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int,
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

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(self.chat_completions_url, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:600]
            raise RuntimeError(
                f"LLM API HTTP {exc.response.status_code}, url={self.chat_completions_url}, body={detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"LLM API request failed: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"LLM API returned non-JSON response: {exc}") from exc

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

    return OpenAICompatibleCrewAILLM(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
    )


def run_crewai_session(payload: CrewRunPayload) -> dict[str, Any]:
    """启动 4 Agent CrewAI 协作过程，返回可记录的执行摘要。"""
    llm = build_crewai_llm()

    data_agent = Agent(
        role="数据分析Agent",
        goal="分析商品数据趋势并给出价格建议",
        backstory="擅长销量、转化率和利润弹性分析。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    market_agent = Agent(
        role="市场情报Agent",
        goal="基于竞品样本判断市场价格带",
        backstory="擅长比较同类商品的市场价格水平。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    risk_agent = Agent(
        role="风控Agent",
        goal="校验利润率和价格上下限约束",
        backstory="擅长识别价格决策中的经营风险。",
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    manager_agent = Agent(
        role="经理协调Agent",
        goal="综合三方意见输出最终决策",
        backstory="负责多 Agent 结果整合和冲突裁决。",
        llm=llm,
        verbose=False,
        allow_delegation=True,
    )

    product = payload.product
    base_context = (
        f"商品={product.product_name}; 当前价={money(product.current_price)}; "
        f"成本={money(product.cost_price)}; 库存={product.stock}; 策略={payload.strategy_goal}; "
        f"约束={payload.constraints}"
    )

    data_task = Task(
        description=f"请完成数据分析并给出建议价格区间。上下文：{base_context}",
        expected_output="包含价格区间、预估销量、预估利润、置信度的中文摘要。",
        agent=data_agent,
    )
    market_task = Task(
        description=f"请完成市场价带分析并给出建议价格。上下文：{base_context}",
        expected_output="包含市场底价、市场上限、建议价、样本规模的中文摘要。",
        agent=market_agent,
        context=[data_task],
    )
    risk_task = Task(
        description=f"请评估候选价格风险并给出风控建议。上下文：{base_context}",
        expected_output="包含是否通过、风险等级、安全底价、是否人工复核的中文摘要。",
        agent=risk_agent,
        context=[data_task, market_task],
    )
    manager_task = Task(
        description="请综合数据、市场、风控三方意见，给出最终定价建议与执行策略。",
        expected_output="包含最终价格、执行策略、结论摘要。",
        agent=manager_agent,
        context=[data_task, market_task, risk_task],
    )

    crew = Crew(
        name="pricing-multi-agent-crew",
        agents=[data_agent, market_agent, risk_agent],
        manager_agent=manager_agent,
        tasks=[data_task, market_task, risk_task, manager_task],
        process=Process.hierarchical,
        verbose=False,
    )
    output = crew.kickoff(
        inputs={
            "task_id": payload.task_id,
            "product_id": product.product_id,
            "strategy_goal": payload.strategy_goal,
            "baseline_sales": payload.baseline_sales,
            "baseline_profit": str(payload.baseline_profit),
        }
    )

    return {
        "enabled": True,
        "process": "hierarchical",
        "taskCount": 4,
        "llmModel": llm.model,
        "llmBaseUrl": llm.base_url,
        "agentRoles": [data_agent.role, market_agent.role, risk_agent.role, manager_agent.role],
        "crewOutput": str(output),
    }
