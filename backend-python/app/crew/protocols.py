from dataclasses import dataclass
from decimal import Decimal

from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot


@dataclass(slots=True)
class CrewRunPayload:
    task_id: int
    strategy_goal: str
    constraints: dict
    product: ProductContext
    metrics: list[DailyMetricSnapshot]
    traffic: list[TrafficSnapshot]
    baseline_sales: int
    baseline_profit: Decimal

