from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class CrewDataAnalysisOutput(BaseModel):
    sales_trend: Literal["rapid_rising", "rising", "stable", "declining", "rapid_declining"] = Field(
        "stable",
        description="Trend category inferred from 7/30/90 day sales history.",
    )
    sales_trend_score: float = Field(0.0, description="Normalized score in [-1, 1], higher means stronger growth.")
    inventory_status: Literal["severe_overstock", "overstock", "normal", "tight", "shortage"] = Field(
        "normal",
        description="Inventory pressure category inferred from stock and turnover.",
    )
    inventory_health_score: float = Field(50.0, ge=0.0, le=100.0, description="Inventory health score in [0, 100].")
    estimated_turnover_days: Optional[int] = None
    demand_elasticity: Optional[float] = None
    recommended_action: Literal["maintain", "discount", "clearance"] = Field(
        "maintain",
        description="Action proposal from the data perspective only.",
    )
    recommended_discount_min: float = Field(1.0, ge=0.5, le=1.5)
    recommended_discount_max: float = Field(1.0, ge=0.5, le=1.5)
    recommendation_confidence: float = Field(0.5, ge=0.0, le=1.0)
    recommendation_reasons: List[str] = Field(default_factory=list)
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""


class CrewMarketIntelOutput(BaseModel):
    competition_level: Literal["fierce", "moderate", "low"] = Field(
        "moderate",
        description="Competition intensity in the target segment.",
    )
    competition_score: float = Field(0.5, ge=0.0, le=1.0)
    price_position: Literal["premium", "mid-range", "budget"] = Field(
        "mid-range",
        description="Current product price position versus competitors.",
    )
    price_percentile: float = Field(0.5, ge=0.0, le=1.0)
    min_competitor_price: Optional[float] = None
    max_competitor_price: Optional[float] = None
    avg_competitor_price: Optional[float] = None
    price_gap_vs_avg: Optional[float] = None
    market_suggestion: Literal["price_war", "penetrate", "discount", "differentiate", "premium", "maintain"] = "maintain"
    suggestion_confidence: float = Field(0.5, ge=0.0, le=1.0)
    suggestion_reasons: List[str] = Field(default_factory=list)
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""


class CrewRiskControlOutput(BaseModel):
    current_profit_margin: float = 0.0
    profit_margin_after_discount: Optional[float] = None
    break_even_price: float = 0.0
    min_safe_price: float = 0.0
    required_min_price: float = 0.0
    current_price_compliant: bool = True
    risk_level: Literal["high", "medium", "low"] = Field(
        "medium",
        description="Risk level after evaluating margin/compliance/constraints.",
    )
    risk_score: float = Field(50.0, ge=0.0, le=100.0)
    allow_promotion: bool = False
    max_safe_discount: float = Field(1.0, ge=0.5, le=1.5)
    recommendation: Literal["maintain", "discount", "increase"] = Field(
        "maintain",
        description="Risk-side recommendation under hard constraints.",
    )
    recommendation_reasons: List[str] = Field(default_factory=list)
    constraint_summary: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    veto_reason: Optional[str] = None
    thinking_process: str = ""
    reasoning: str = ""
    decision_summary: str = ""


class CrewManagerDecisionOutput(BaseModel):
    decision: Literal["maintain", "discount", "increase"] = Field(
        "maintain",
        description="Final management decision after conflict resolution.",
    )
    discount_rate: float = Field(1.0, ge=0.5, le=1.5)
    suggested_price: float = 0.0
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    core_reasons: str = "No clear reasons were generated."
    key_factors: List[str] = Field(default_factory=list)
    risk_warning: str = "No explicit risk warning."
    contingency_plan: str = "Monitor KPIs and re-run decision if abnormal."
    conflict_summary: str = ""
    thinking_process: str = ""
    reasoning: str = ""
