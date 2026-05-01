"""智能体输出 Schema，约束各 Agent 返回 JSON 的结构。"""

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.utils.text_utils import MANUAL_REVIEW_STRATEGY

assert MANUAL_REVIEW_STRATEGY == "人工审核"


class ProductContext(BaseModel):
    product_id: int = Field(alias="productId")
    shop_id: int = Field(alias="shopId")
    product_name: str = Field(alias="productName")
    category_name: str | None = Field(default=None, alias="categoryName")
    current_price: Decimal = Field(alias="currentPrice")
    cost_price: Decimal = Field(alias="costPrice")
    stock: int


class DailyMetricSnapshot(BaseModel):
    stat_date: date = Field(alias="statDate")
    visitor_count: int = Field(alias="visitorCount")
    add_cart_count: int = Field(alias="addCartCount")
    pay_buyer_count: int = Field(alias="payBuyerCount")
    sales_count: int = Field(alias="salesCount")
    turnover: Decimal
    conversion_rate: Decimal = Field(alias="conversionRate")


class TrafficSnapshot(BaseModel):
    stat_date: date = Field(alias="statDate")
    traffic_source: str = Field(alias="trafficSource")
    impression_count: int = Field(alias="impressionCount")
    click_count: int = Field(alias="clickCount")
    visitor_count: int = Field(alias="visitorCount")
    pay_amount: Decimal = Field(alias="payAmount")
    roi: Decimal


class AgentOpinionEvidence(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: str
    label: str
    value: Any
    source: str | None = None


class AgentOpinionPricing(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recommended_price: Decimal | None = Field(default=None, alias="recommendedPrice")
    min_price: Decimal | None = Field(default=None, alias="minPrice")
    max_price: Decimal | None = Field(default=None, alias="maxPrice")
    safe_floor_price: Decimal | None = Field(default=None, alias="safeFloorPrice")


class AgentOpinionImpact(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    expected_sales: int | None = Field(default=None, alias="expectedSales")
    expected_profit: Decimal | None = Field(default=None, alias="expectedProfit")
    profit_growth: Decimal | None = Field(default=None, alias="profitGrowth")


class AgentOpinionMarket(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    market_floor: Decimal | None = Field(default=None, alias="marketFloor")
    market_ceiling: Decimal | None = Field(default=None, alias="marketCeiling")
    market_median: Decimal | None = Field(default=None, alias="marketMedian")
    market_average: Decimal | None = Field(default=None, alias="marketAverage")
    valid_competitor_count: int | None = Field(default=None, alias="validCompetitorCount")
    data_quality: str | None = Field(default=None, alias="dataQuality")
    source_status: str | None = Field(default=None, alias="sourceStatus")


class AgentOpinionRisk(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    is_pass: bool | None = Field(default=None, alias="isPass")
    risk_level: str | None = Field(default=None, alias="riskLevel")
    need_manual_review: bool | None = Field(default=None, alias="needManualReview")


class AgentOpinionRationale(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    thinking: str = ""
    assumptions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AgentOpinionRelations(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    depends_on_opinion_ids: list[str] = Field(default_factory=list, alias="dependsOnOpinionIds")
    accepted_opinion_ids: list[str] = Field(default_factory=list, alias="acceptedOpinionIds")
    rejected_opinion_ids: list[str] = Field(default_factory=list, alias="rejectedOpinionIds")
    conflict_opinion_ids: list[str] = Field(default_factory=list, alias="conflictOpinionIds")
    selected_opinion_ids: list[str] = Field(default_factory=list, alias="selectedOpinionIds")


class AgentOpinionDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    decision_type: Literal["FOLLOW", "OVERRIDE", "MERGE", "REJECT_ALL"] | None = Field(default=None, alias="decisionType")
    consensus_score: float | None = Field(default=None, ge=0.0, le=1.0, alias="consensusScore")
    arbitration_decision: str | None = Field(default=None, alias="arbitrationDecision")
    arbitration_reason: str | None = Field(default=None, alias="arbitrationReason")


class AgentOpinionV1(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    version: Literal["v1"] = "v1"
    opinion_id: str = Field(alias="opinionId")
    task_id: int = Field(alias="taskId")
    run_attempt: int = Field(alias="runAttempt", ge=0)
    agent_code: Literal["DATA_ANALYSIS", "MARKET_INTEL", "RISK_CONTROL", "MANAGER_COORDINATOR"] = Field(alias="agentCode")
    agent_name: str = Field(alias="agentName")
    kind: Literal["PRICE_PROPOSAL", "MARKET_ASSESSMENT", "RISK_ASSESSMENT", "ARBITRATION", "SYSTEM_VERIFICATION"]
    status: Literal["PROPOSED", "ACCEPTED", "REJECTED", "MERGED", "BLOCKED"]
    summary: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    pricing: AgentOpinionPricing | None = None
    impact: AgentOpinionImpact | None = None
    market: AgentOpinionMarket | None = None
    risk: AgentOpinionRisk | None = None
    evidence: list[AgentOpinionEvidence] = Field(default_factory=list)
    rationale: AgentOpinionRationale = Field(default_factory=AgentOpinionRationale)
    relations: AgentOpinionRelations = Field(default_factory=AgentOpinionRelations)
    decision: AgentOpinionDecision | None = None


class DataAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    suggested_price: Decimal = Field(alias="suggestedPrice")
    suggested_min_price: Decimal = Field(alias="suggestedMinPrice")
    suggested_max_price: Decimal = Field(alias="suggestedMaxPrice")
    expected_sales: int = Field(alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    confidence: float = Field(ge=0.0, le=1.0)
    thinking: str
    summary: str
    agent_opinion: AgentOpinionV1 | None = Field(default=None, alias="agentOpinion")


class CompetitorItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    competitor_name: str = Field(alias="competitorName")
    source_platform: str | None = Field(default=None, alias="sourcePlatform")
    shop_type: str | None = Field(default=None, alias="shopType")
    price: Decimal
    original_price: Decimal | None = Field(default=None, alias="originalPrice")
    promotion_tag: str | None = Field(default=None, alias="promotionTag")
    sales_volume_hint: str | None = Field(default=None, alias="salesVolumeHint")


class MarketAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    suggested_price: Decimal = Field(alias="suggestedPrice")
    market_floor: Decimal = Field(alias="marketFloor")
    market_ceiling: Decimal = Field(alias="marketCeiling")
    market_median: Decimal = Field(alias="marketMedian")
    market_average: Decimal = Field(alias="marketAverage")
    confidence: float = Field(ge=0.0, le=1.0)
    thinking: str
    summary: str
    competitor_samples: int = Field(alias="competitorSamples")
    competitors: list[CompetitorItem] | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0, alias="confidenceScore")
    market_score: float | None = Field(default=None, ge=0.0, alias="marketScore")
    source: str | None = None
    source_status: str | None = Field(default=None, alias="sourceStatus")
    raw_item_count: int | None = Field(default=None, alias="rawItemCount")
    filtered_item_count: int | None = Field(default=None, alias="filteredItemCount")
    valid_competitor_count: int | None = Field(default=None, alias="validCompetitorCount")
    data_quality: str | None = Field(default=None, alias="dataQuality")
    quality_reasons: list[str] | None = Field(default=None, alias="qualityReasons")
    pricing_position: str | None = Field(default=None, alias="pricingPosition")
    used_competitor_count: int | None = Field(default=None, alias="usedCompetitorCount")
    risk_notes: str | None = Field(default=None, alias="riskNotes")
    evidence_summary: str | None = Field(default=None, alias="evidenceSummary")
    brand_breakdown: list[dict] | None = Field(default=None, alias="brandBreakdown")
    shop_type_breakdown: list[dict] | None = Field(default=None, alias="shopTypeBreakdown")
    sales_weighted_average: float | None = Field(default=None, alias="salesWeightedAverage")
    sales_weighted_median: float | None = Field(default=None, alias="salesWeightedMedian")
    promotion_density: dict | None = Field(default=None, alias="promotionDensity")
    agent_opinion: AgentOpinionV1 | None = Field(default=None, alias="agentOpinion")


class RiskAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_pass: bool = Field(alias="isPass")
    safe_floor_price: Decimal = Field(alias="safeFloorPrice")
    suggested_price: Decimal = Field(alias="suggestedPrice")
    risk_level: Literal["LOW", "HIGH"] = Field(alias="riskLevel")
    need_manual_review: bool = Field(alias="needManualReview")
    thinking: str
    summary: str
    agent_opinion: AgentOpinionV1 | None = Field(default=None, alias="agentOpinion")


class ManagerAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    final_price: Decimal = Field(alias="finalPrice")
    expected_sales: int = Field(alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    profit_growth: Decimal = Field(alias="profitGrowth")
    execute_strategy: Literal["人工审核"] = Field(alias="executeStrategy")
    is_pass: bool = Field(alias="isPass")
    thinking: str
    result_summary: str = Field(alias="resultSummary")
    suggested_min_price: Decimal = Field(alias="suggestedMinPrice")
    suggested_max_price: Decimal = Field(alias="suggestedMaxPrice")
    consensus_score: float | None = Field(default=None, ge=0.0, le=1.0, alias="consensusScore")
    disagreement_summary: str | None = Field(default=None, alias="disagreementSummary")
    disagreement_points: list[str | dict[str, Any]] | None = Field(default=None, alias="disagreementPoints")
    accepted_opinions: list[str] | None = Field(default=None, alias="acceptedOpinions")
    rejected_opinions: list[str] | None = Field(default=None, alias="rejectedOpinions")
    arbitration_decision: str | None = Field(default=None, alias="arbitrationDecision")
    arbitration_reason: str | None = Field(default=None, alias="arbitrationReason")
    selected_agent: Literal["DATA_ANALYSIS", "MARKET_INTEL", "RISK_CONTROL"] | None = Field(default=None, alias="selectedAgent")
    selected_price: Decimal | None = Field(default=None, alias="selectedPrice")
    selected_strategy: str | None = Field(default=None, alias="selectedStrategy")
    agent_opinion: AgentOpinionV1 | None = Field(default=None, alias="agentOpinion")
