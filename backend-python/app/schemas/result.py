"""最终定价结果 Schema，约束落库和返回给 Java 的结果格式。"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TaskFinalResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: int = Field(alias="taskId")
    final_price: Decimal = Field(alias="finalPrice")
    expected_sales: int = Field(alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    profit_growth: Decimal = Field(alias="profitGrowth")
    is_pass: bool = Field(alias="isPass")
    execute_strategy: str = Field(alias="executeStrategy")
    result_summary: str = Field(alias="resultSummary")
    suggested_min_price: Decimal = Field(alias="suggestedMinPrice")
    suggested_max_price: Decimal = Field(alias="suggestedMaxPrice")
