"""请求与响应数据模型模块，统一定义 API 与智能体结构化协议。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    product_id: str
    product_name: str
    category: str
    current_price: float
    cost: float
    original_price: Optional[float] = None
    stock: int
    stock_age_days: int = 0
    is_new_product: bool = False
    is_seasonal: bool = False
    product_lifecycle_stage: Optional[str] = None


class SalesData(BaseModel):
    sales_history_7d: List[int] = Field(default_factory=list)
    sales_history_30d: List[int] = Field(default_factory=list)
    sales_history_90d: List[int] = Field(default_factory=list)
    pv_7d: List[int] = Field(default_factory=list)
    uv_7d: List[int] = Field(default_factory=list)
    conversion_rate_7d: Optional[float] = None
    promotion_history: List[Dict[str, Any]] = Field(default_factory=list)


class CompetitorInfo(BaseModel):
    competitor_id: str
    product_name: str
    current_price: float
    original_price: Optional[float] = None
    sales_volume: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    shop_type: Optional[str] = None
    is_self_operated: bool = False
    promotion_tags: List[str] = Field(default_factory=list)


class CompetitorData(BaseModel):
    competitors: List[CompetitorInfo] = Field(default_factory=list)
    category_total_sales: Optional[int] = None
    category_total_gmv: Optional[float] = None
    top_3_brand_share: Optional[float] = None
    upcoming_platform_events: List[Dict[str, Any]] = Field(default_factory=list)


class ReviewData(BaseModel):
    rating: int
    content: str
    tags: List[str] = Field(default_factory=list)
    date: Optional[str] = None


class RiskData(BaseModel):
    min_profit_margin: float = 0.15
    min_profit_markup: Optional[float] = None
    target_profit_margin: float = 0.30
    refund_rate: float = 0.0
    complaint_rate: float = 0.0
    cost_breakdown: Optional[Dict[str, float]] = None
    cash_conversion_cycle: Optional[int] = None
    max_discount_allowed: Optional[float] = None
    price_floor: Optional[float] = None
    price_ceiling: Optional[float] = None
    is_brand_controlled: bool = False
    enforce_hard_constraints: bool = True
    constraint_summary: List[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    task_id: str
    product: ProductBase
    sales_data: SalesData
    competitor_data: CompetitorData
    risk_data: RiskData
    customer_reviews: List[ReviewData] = Field(default_factory=list)
    strategy_goal: str = "MAX_PROFIT"
    strategy_constraints: Optional[str] = None
    business_context: Dict[str, Any] = Field(default_factory=dict)


class DataAnalysisResult(BaseModel):
    sales_trend: str
    sales_trend_score: float
    inventory_status: str
    inventory_health_score: float
    estimated_turnover_days: Optional[int] = None
    demand_elasticity: Optional[float] = None
    demand_elasticity_confidence: Optional[float] = None
    product_lifecycle_stage: Optional[str] = None
    lifecycle_evidence: Optional[str] = None
    has_anomalies: bool = False
    anomaly_list: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_action: str = "maintain"
    recommended_discount_range: Tuple[float, float] = (1.0, 1.0)
    recommendation_confidence: float = 0.5
    recommendation_reasons: List[str] = Field(default_factory=list)
    analysis_details: Dict[str, Any] = Field(default_factory=dict)
    data_quality_score: float = 1.0
    limitations: List[str] = Field(default_factory=list)
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""
    confidence: float = 0.5


class MarketIntelResult(BaseModel):
    competition_level: str
    competition_score: float
    price_position: str
    price_percentile: float
    min_competitor_price: Optional[float] = None
    max_competitor_price: Optional[float] = None
    avg_competitor_price: Optional[float] = None
    price_gap_vs_avg: Optional[float] = None
    active_competitor_promotions: List[Dict[str, Any]] = Field(default_factory=list)
    upcoming_events: List[Dict[str, Any]] = Field(default_factory=list)
    sentiment_score: float = 0.0
    sentiment_label: str = "neutral"
    top_positive_keywords: List[str] = Field(default_factory=list)
    top_negative_keywords: List[str] = Field(default_factory=list)
    estimated_market_share: Optional[float] = None
    market_share_trend: Optional[str] = None
    market_suggestion: str = "maintain"
    suggestion_confidence: float = 0.5
    suggestion_reasons: List[str] = Field(default_factory=list)
    analysis_details: Dict[str, Any] = Field(default_factory=dict)
    data_sources: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""
    confidence: float = 0.5


class RiskControlResult(BaseModel):
    current_profit_margin: float
    profit_margin_after_discount: Optional[float] = None
    break_even_price: float
    min_safe_price: float
    required_min_price: float
    absolute_price_floor: Optional[float] = None
    current_price_compliant: bool = True
    risk_level: str = "medium"
    risk_score: float = 50.0
    risk_breakdown: Dict[str, float] = Field(default_factory=dict)
    allow_promotion: bool = False
    max_safe_discount: float = 1.0
    discount_conditions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    recommendation: str = "maintain"
    recommendation_reasons: List[str] = Field(default_factory=list)
    constraint_summary: List[str] = Field(default_factory=list)
    calculation_details: Dict[str, Any] = Field(default_factory=dict)
    compliance_check: bool = True
    veto_reason: Optional[str] = None
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""
    confidence: float = 0.5


class AgentSummary(BaseModel):
    agent_name: str
    summary: str
    key_points: List[str] = Field(default_factory=list)


class ConflictResolution(BaseModel):
    agent1: str
    agent2: str
    conflict: str
    resolution: str
    priority: str


class ExpectedOutcomes(BaseModel):
    sales_lift: float
    profit_change: float
    market_share_change: float = 0.0


class ExecutionPlan(BaseModel):
    step: int
    action: str
    timing: str
    responsible: str


class FinalDecision(BaseModel):
    decision: str
    discount_rate: float
    suggested_price: float
    confidence: float
    expected_outcomes: Optional[ExpectedOutcomes] = None
    core_reasons: str
    key_factors: List[str] = Field(default_factory=list)
    conflicts_detected: List[ConflictResolution] = Field(default_factory=list)
    risk_warning: str
    contingency_plan: str
    execution_plan: List[ExecutionPlan] = Field(default_factory=list)
    report_text: str
    agent_summaries: List[AgentSummary] = Field(default_factory=list)
    decision_framework: str
    alternative_options: List[Dict[str, Any]] = Field(default_factory=list)
    thinking_process: str = ""
    reasoning: str = ""
    conflict_summary: str = ""
    warnings: List[str] = Field(default_factory=list)
    agent_summaries_structured: Dict[str, Any] = Field(default_factory=dict)


class DecisionResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[FinalDecision] = None
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class DecisionTaskRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    task_id: Optional[int] = Field(default=None, validation_alias=AliasChoices("task_id", "taskId"))
    product_ids: List[int] = Field(default_factory=list, validation_alias=AliasChoices("product_ids", "productIds"))
    strategy_goal: str = Field(default="", validation_alias=AliasChoices("strategy_goal", "strategyGoal"))
    constraints: str = ""
