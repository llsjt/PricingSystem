"""智能体输出 Schema，约束各 Agent 返回 JSON 的结构。"""

from datetime import date
from decimal import Decimal
from typing import Literal

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


class RiskAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    is_pass: bool = Field(alias="isPass")
    safe_floor_price: Decimal = Field(alias="safeFloorPrice")
    suggested_price: Decimal = Field(alias="suggestedPrice")
    risk_level: Literal["LOW", "HIGH"] = Field(alias="riskLevel")
    need_manual_review: bool = Field(alias="needManualReview")
    thinking: str
    summary: str


class ManagerAgentOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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
