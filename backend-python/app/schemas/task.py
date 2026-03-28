from pydantic import BaseModel, ConfigDict, Field, model_validator


class DispatchTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: int = Field(alias="taskId")
    product_id: int | None = Field(default=None, alias="productId")
    product_ids: list[int] = Field(default_factory=list, alias="productIds")
    strategy_goal: str = Field(default="MAX_PROFIT", alias="strategyGoal")
    constraints: str = Field(default="")
    trace_id: str | None = Field(default=None, alias="traceId")

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

