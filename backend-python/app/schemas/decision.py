from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ProductBase(BaseModel):
    product_id: str = Field(..., description="Unique product id")
    product_name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    sub_category: Optional[str] = Field(None, description="Optional sub category")
    current_price: float = Field(..., description="Current selling price")
    cost: float = Field(..., description="Product cost")
    original_price: Optional[float] = Field(None, description="Original listed price")
    stock: int = Field(..., description="Current stock")
    stock_age_days: Optional[int] = Field(0, description="Stock age in days")
    is_new_product: bool = Field(False, description="Whether the product is new")
    is_seasonal: bool = Field(False, description="Whether the product is seasonal")
    product_lifecycle_stage: Optional[str] = Field(
        None,
        description="Lifecycle stage such as introduction, growth, maturity, decline",
    )


class SalesData(BaseModel):
    sales_history_7d: List[int] = Field(default_factory=list, description="Sales for the last 7 days")
    sales_history_30d: List[int] = Field(default_factory=list, description="Sales for the last 30 days")
    sales_history_90d: List[int] = Field(default_factory=list, description="Sales for the last 90 days")
    pv_7d: List[int] = Field(default_factory=list, description="Page views for the last 7 days")
    uv_7d: List[int] = Field(default_factory=list, description="Unique visitors for the last 7 days")
    conversion_rate_7d: Optional[float] = Field(None, description="Conversion rate for the last 7 days")
    promotion_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Historical promotion records",
    )


class CompetitorInfo(BaseModel):
    competitor_id: str = Field(..., description="Competitor id")
    product_name: str = Field(..., description="Competitor product name")
    current_price: float = Field(..., description="Competitor current price")
    original_price: Optional[float] = Field(None, description="Competitor original price")
    sales_volume: Optional[int] = Field(None, description="Competitor sales volume")
    rating: Optional[float] = Field(None, description="Competitor rating")
    review_count: Optional[int] = Field(None, description="Competitor review count")
    shop_type: Optional[str] = Field(None, description="Store type")
    is_self_operated: bool = Field(False, description="Whether self operated")
    promotion_tags: List[str] = Field(default_factory=list, description="Promotion tags")


class CompetitorData(BaseModel):
    competitors: List[CompetitorInfo] = Field(default_factory=list, description="Competitor list")
    category_total_sales: Optional[int] = Field(None, description="Total category sales")
    category_total_gmv: Optional[float] = Field(None, description="Total category GMV")
    top_3_brand_share: Optional[float] = Field(None, description="CR3 share")
    upcoming_platform_events: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Upcoming platform events",
    )


class ReviewData(BaseModel):
    rating: int = Field(..., description="Rating from 1 to 5")
    content: str = Field(..., description="Review content")
    tags: List[str] = Field(default_factory=list, description="Review tags")
    date: Optional[str] = Field(None, description="Review date")


class RiskData(BaseModel):
    min_profit_margin: float = Field(default=0.15, description="Minimum acceptable margin")
    min_profit_markup: Optional[float] = Field(None, description="Minimum profit markup based on cost")
    target_profit_margin: Optional[float] = Field(0.30, description="Target profit margin")
    refund_rate: float = Field(default=0.0, description="Refund rate")
    complaint_rate: float = Field(default=0.0, description="Complaint rate")
    cost_breakdown: Optional[Dict[str, float]] = Field(None, description="Detailed cost breakdown")
    cash_conversion_cycle: Optional[int] = Field(None, description="Cash conversion cycle")
    max_discount_allowed: Optional[float] = Field(None, description="External max allowed discount rate")
    price_floor: Optional[float] = Field(None, description="Absolute price floor")
    price_ceiling: Optional[float] = Field(None, description="Absolute price ceiling")
    is_brand_controlled: bool = Field(False, description="Whether the price is brand controlled")
    enforce_hard_constraints: bool = Field(True, description="Whether hard constraints must be enforced")
    constraint_summary: List[str] = Field(default_factory=list, description="Parsed constraint summary")


class AnalysisRequest(BaseModel):
    task_id: str = Field(..., description="Task id")
    product: ProductBase
    sales_data: SalesData
    competitor_data: CompetitorData
    risk_data: RiskData
    customer_reviews: List[ReviewData] = Field(default_factory=list, description="Customer reviews")
    strategy_goal: str = Field(
        default="MAX_PROFIT",
        description="Strategy goal such as MAX_PROFIT, CLEARANCE, MARKET_SHARE, BRAND_BUILDING",
    )
    strategy_constraints: Optional[str] = Field(None, description="Strategy constraints")
    business_context: Dict[str, Any] = Field(default_factory=dict, description="Additional business context")


class DataAnalysisResult(BaseModel):
    sales_trend: str = Field(..., description="Sales trend label")
    sales_trend_score: float = Field(..., description="Sales trend score")
    inventory_status: str = Field(..., description="Inventory status")
    inventory_health_score: float = Field(..., description="Inventory health score")
    estimated_turnover_days: Optional[int] = Field(None, description="Estimated turnover days")

    demand_elasticity: Optional[float] = Field(None, description="Demand elasticity")
    demand_elasticity_confidence: Optional[float] = Field(None, description="Elasticity confidence")
    product_lifecycle_stage: Optional[str] = Field(None, description="Lifecycle stage")
    lifecycle_evidence: Optional[str] = Field(None, description="Lifecycle evidence")

    has_anomalies: bool = Field(False, description="Whether anomalies exist")
    anomaly_list: List[Dict[str, Any]] = Field(default_factory=list, description="Detected anomalies")

    recommended_action: str = Field(..., description="Recommended action")
    recommended_discount_range: Tuple[float, float] = Field(..., description="Recommended price-rate range")
    recommendation_confidence: float = Field(..., description="Recommendation confidence")
    recommendation_reasons: List[str] = Field(default_factory=list, description="Recommendation reasons")

    analysis_details: Optional[Dict[str, Any]] = Field(None, description="Detailed analysis")
    data_quality_score: float = Field(1.0, description="Data quality score")
    limitations: List[str] = Field(default_factory=list, description="Analysis limitations")

    thinking_process: str = Field("", description="Agent thinking process")
    reasoning: str = Field("", description="Agent reasoning")
    decision_summary: str = Field("", description="Agent decision summary")
    confidence: float = Field(0.0, description="Unified confidence field for streaming")


class MarketIntelResult(BaseModel):
    competition_level: str = Field(..., description="Competition level")
    competition_score: float = Field(..., description="Competition score")
    price_position: str = Field(..., description="Price position")
    price_percentile: float = Field(..., description="Price percentile")

    min_competitor_price: Optional[float] = Field(None, description="Minimum competitor price")
    max_competitor_price: Optional[float] = Field(None, description="Maximum competitor price")
    avg_competitor_price: Optional[float] = Field(None, description="Average competitor price")
    price_gap_vs_avg: Optional[float] = Field(None, description="Gap versus average competitor price")

    active_competitor_promotions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Active competitor promotions",
    )
    upcoming_events: List[Dict[str, Any]] = Field(default_factory=list, description="Upcoming events")

    sentiment_score: float = Field(0.0, description="Sentiment score")
    sentiment_label: str = Field("neutral", description="Sentiment label")
    top_positive_keywords: List[str] = Field(default_factory=list, description="Positive keywords")
    top_negative_keywords: List[str] = Field(default_factory=list, description="Negative keywords")

    estimated_market_share: Optional[float] = Field(None, description="Estimated market share")
    market_share_trend: Optional[str] = Field(None, description="Market share trend")

    market_suggestion: str = Field(..., description="Market suggestion")
    suggestion_confidence: float = Field(..., description="Suggestion confidence")
    suggestion_reasons: List[str] = Field(default_factory=list, description="Suggestion reasons")

    analysis_details: Optional[Dict[str, Any]] = Field(None, description="Detailed analysis")
    data_sources: List[str] = Field(default_factory=list, description="Data sources")
    limitations: List[str] = Field(default_factory=list, description="Analysis limitations")

    thinking_process: str = Field("", description="Agent thinking process")
    reasoning: str = Field("", description="Agent reasoning")
    decision_summary: str = Field("", description="Agent decision summary")
    confidence: float = Field(0.0, description="Unified confidence field for streaming")


class RiskControlResult(BaseModel):
    current_profit_margin: float = Field(..., description="Current profit margin")
    profit_margin_after_discount: Optional[float] = Field(None, description="Profit margin after discount")

    break_even_price: float = Field(..., description="Break-even price")
    min_safe_price: float = Field(..., description="Minimum safe price")
    required_min_price: float = Field(..., description="Required minimum executable price after applying constraints")
    absolute_price_floor: Optional[float] = Field(None, description="Absolute price floor")
    current_price_compliant: bool = Field(True, description="Whether current price satisfies hard constraints")

    risk_level: str = Field(..., description="Risk level")
    risk_score: float = Field(..., description="Risk score")
    risk_breakdown: Dict[str, float] = Field(default_factory=dict, description="Risk breakdown")

    allow_promotion: bool = Field(..., description="Whether promotion is allowed")
    max_safe_discount: float = Field(..., description="Maximum safe price rate after discount")
    discount_conditions: List[str] = Field(default_factory=list, description="Discount conditions")

    warnings: List[str] = Field(default_factory=list, description="Warnings")
    recommendation: str = Field(..., description="Recommendation")
    recommendation_reasons: List[str] = Field(default_factory=list, description="Recommendation reasons")
    constraint_summary: List[str] = Field(default_factory=list, description="Constraint summary")

    calculation_details: Optional[Dict[str, Any]] = Field(None, description="Calculation details")
    compliance_check: bool = Field(True, description="Compliance check result")
    veto_reason: Optional[str] = Field(None, description="Veto reason")

    thinking_process: str = Field("", description="Agent thinking process")
    reasoning: str = Field("", description="Agent reasoning")
    decision_summary: str = Field("", description="Agent decision summary")
    confidence: float = Field(0.0, description="Unified confidence field for streaming")


class AgentSummary(BaseModel):
    agent_name: str
    summary: str
    key_points: List[str] = Field(default_factory=list, description="Key points")


class ConflictResolution(BaseModel):
    agent1: str
    agent2: str
    conflict: str
    resolution: str
    priority: str


class ExpectedOutcomes(BaseModel):
    sales_lift: float = Field(..., description="Expected sales lift multiplier")
    profit_change: float = Field(..., description="Expected profit change")
    market_share_change: float = Field(0.0, description="Expected market share change")


class ExecutionPlan(BaseModel):
    step: int
    action: str
    timing: str
    responsible: str


class FinalDecision(BaseModel):
    decision: str = Field(..., description="Final decision code")
    discount_rate: float = Field(..., description="Final price rate after discount")
    suggested_price: float = Field(..., description="Suggested price")
    confidence: float = Field(..., description="Final confidence")

    expected_outcomes: Optional[ExpectedOutcomes] = Field(None, description="Expected outcomes")

    core_reasons: str = Field(..., description="Core decision reasons")
    key_factors: List[str] = Field(default_factory=list, description="Key factors")

    conflicts_detected: List[ConflictResolution] = Field(
        default_factory=list,
        description="Detected conflicts and resolutions",
    )

    risk_warning: str = Field(..., description="Risk warning summary")
    contingency_plan: str = Field(..., description="Contingency plan")
    execution_plan: List[ExecutionPlan] = Field(default_factory=list, description="Execution plan")

    report_text: str = Field(..., description="Full report text")
    agent_summaries: List[AgentSummary] = Field(default_factory=list, description="Agent summaries")
    decision_framework: str = Field(..., description="Decision framework summary")
    alternative_options: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Alternative options that were considered",
    )

    thinking_process: str = Field("", description="Manager thinking process")
    reasoning: str = Field("", description="Manager reasoning")
    conflict_summary: str = Field("", description="Conflict summary")
    warnings: List[str] = Field(default_factory=list, description="Warnings for the final decision")
    agent_summaries_structured: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured agent summary object for frontend display",
    )


class DecisionResponse(BaseModel):
    task_id: str = Field(..., description="Task id")
    status: str = Field(..., description="Status")
    result: Optional[FinalDecision] = None
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
