from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DispatchTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: int = Field(alias="taskId")
    product_id: int | None = Field(default=None, alias="productId")
    product_ids: list[int] = Field(default_factory=list, alias="productIds")
    strategy_goal: str = Field(default="MAX_PROFIT", alias="strategyGoal")
    constraints: str = Field(default="")
    trace_id: str | None = Field(default=None, alias="traceId")
    llm_api_key: str | None = Field(default=None, alias="llmApiKey")
    llm_base_url: str | None = Field(default=None, alias="llmBaseUrl")
    llm_model: str | None = Field(default=None, alias="llmModel")

    @model_validator(mode="after")
    def normalize_product_id(self) -> "DispatchTaskRequest":
        if self.product_id is None and self.product_ids:
            self.product_id = self.product_ids[0]
        if self.product_id is None:
            raise ValueError("productId/productIds is required")
        return self


class DispatchTaskResponse(BaseModel):
    accepted: bool
    task_id: int = Field(alias="taskId")
    status: str
    message: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class TaskStatusResponse(BaseModel):
    task_id: int = Field(alias="taskId")
    status: str
    has_result: bool = Field(alias="hasResult")
    message: str | None = None

    model_config = ConfigDict(populate_by_name=True)


class RetryTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_id: int | None = Field(default=None, alias="productId")
    strategy_goal: str | None = Field(default=None, alias="strategyGoal")
    constraints: str | None = Field(default=None)


class AgentLogItem(BaseModel):
    id: int
    task_id: int = Field(alias="taskId")
    role_name: str = Field(alias="roleName")
    speak_order: int = Field(alias="speakOrder")
    thought_content: str | None = Field(default=None, alias="thoughtContent")

    # Legacy compatibility fields for current consumers.
    agent_code: str | None = Field(default=None, alias="agentCode")
    agent_name: str | None = Field(default=None, alias="agentName")
    run_attempt: int | None = Field(default=None, alias="runAttempt")
    run_order: int | None = Field(default=None, alias="runOrder")
    display_order: int | None = Field(default=None, alias="displayOrder")
    stage: str | None = None
    run_status: str | None = Field(default=None, alias="runStatus")
    output_summary: str | None = Field(default=None, alias="outputSummary")
    output_payload: dict[str, Any] | None = Field(default=None, alias="outputPayload")
    suggested_price: Decimal | None = Field(default=None, alias="suggestedPrice")
    predicted_profit: Decimal | None = Field(default=None, alias="predictedProfit")
    confidence_score: Decimal | None = Field(default=None, alias="confidenceScore")
    risk_level: str | None = Field(default=None, alias="riskLevel")
    need_manual_review: bool | None = Field(default=None, alias="needManualReview")
    thinking: str | None = None
    evidence: list[dict[str, Any]] | None = None
    suggestion: dict[str, Any] | None = None
    reason_why: str | None = Field(default=None, alias="reasonWhy")
    created_at: datetime = Field(alias="createdAt")

    model_config = ConfigDict(populate_by_name=True)


class TaskLogsResponse(BaseModel):
    task_id: int = Field(alias="taskId")
    total: int
    logs: list[AgentLogItem]

    model_config = ConfigDict(populate_by_name=True)


class TaskResultBrief(BaseModel):
    final_price: Decimal = Field(alias="finalPrice")
    expected_sales: int | None = Field(default=None, alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    profit_growth: Decimal = Field(alias="profitGrowth")
    is_pass: bool = Field(alias="isPass")
    execute_strategy: str | None = Field(default=None, alias="executeStrategy")
    result_summary: str | None = Field(default=None, alias="resultSummary")

    model_config = ConfigDict(populate_by_name=True)


class TaskDetailResponse(BaseModel):
    task_id: int = Field(alias="taskId")
    status: str
    product_id: int = Field(alias="productId")
    current_price: Decimal = Field(alias="currentPrice")
    suggested_min_price: Decimal | None = Field(default=None, alias="suggestedMinPrice")
    suggested_max_price: Decimal | None = Field(default=None, alias="suggestedMaxPrice")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    has_result: bool = Field(alias="hasResult")
    result: TaskResultBrief | None = None

    model_config = ConfigDict(populate_by_name=True)
