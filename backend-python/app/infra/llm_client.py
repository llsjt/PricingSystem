"""Failover-capable CrewAI LLM adapter."""

from __future__ import annotations

from typing import Any

from crewai.llms.base_llm import BaseLLM

from app.crew.crewai_runtime import LLMHttpError, OpenAICompatibleCrewAILLM

RETRYABLE_FAILOVER_STATUSES = {408, 429, 500, 502, 503, 504}


class FailoverCrewAILLM(BaseLLM):
    """Delegate to a backup LLM when the primary channel is exhausted."""

    def __init__(self, *, primary: OpenAICompatibleCrewAILLM, backup: OpenAICompatibleCrewAILLM) -> None:
        super().__init__(
            model=primary.model,
            provider="openai-compatible-failover",
            api_key=primary.api_key,
            base_url=primary.base_url,
            temperature=primary.temperature,
        )
        self.primary = primary
        self.backup = backup

    @staticmethod
    def _should_failover(exc: Exception) -> bool:
        if isinstance(exc, LLMHttpError):
            return exc.status_code in RETRYABLE_FAILOVER_STATUSES
        text = str(exc).lower()
        return any(token in text for token in ("timeout", "request failed", "connection", "temporar", "rate limit"))

    def call(
        self,
        messages: str | list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        callbacks: list[Any] | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Any | None = None,
        from_agent: Any | None = None,
        response_model: type | None = None,
    ) -> str | Any:
        try:
            return self.primary.call(
                messages,
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )
        except Exception as exc:
            if not self._should_failover(exc):
                raise
            return self.backup.call(
                messages,
                tools=tools,
                callbacks=callbacks,
                available_functions=available_functions,
                from_task=from_task,
                from_agent=from_agent,
                response_model=response_model,
            )

