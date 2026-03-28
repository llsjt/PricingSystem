from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


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
    suggested_price: Decimal = Field(alias="suggestedPrice")
    suggested_min_price: Decimal = Field(alias="suggestedMinPrice")
    suggested_max_price: Decimal = Field(alias="suggestedMaxPrice")
    expected_sales: int = Field(alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    confidence: float
    summary: str


class MarketAgentOutput(BaseModel):
    suggested_price: Decimal = Field(alias="suggestedPrice")
    market_floor: Decimal = Field(alias="marketFloor")
    market_ceiling: Decimal = Field(alias="marketCeiling")
    confidence: float
    summary: str
    simulated_samples: int = Field(alias="simulatedSamples")


class RiskAgentOutput(BaseModel):
    is_pass: bool = Field(alias="isPass")
    safe_floor_price: Decimal = Field(alias="safeFloorPrice")
    suggested_price: Decimal = Field(alias="suggestedPrice")
    risk_level: str = Field(alias="riskLevel")
    need_manual_review: bool = Field(alias="needManualReview")
    summary: str


class ManagerAgentOutput(BaseModel):
    final_price: Decimal = Field(alias="finalPrice")
    expected_sales: int = Field(alias="expectedSales")
    expected_profit: Decimal = Field(alias="expectedProfit")
    profit_growth: Decimal = Field(alias="profitGrowth")
    execute_strategy: str = Field(alias="executeStrategy")
    is_pass: bool = Field(alias="isPass")
    result_summary: str = Field(alias="resultSummary")
    suggested_min_price: Decimal = Field(alias="suggestedMinPrice")
    suggested_max_price: Decimal = Field(alias="suggestedMaxPrice")

