from typing import List, Optional
from pydantic import BaseModel, Field

# --- Common Models ---

class ProductInfo(BaseModel):
    product_id: str
    name: str
    current_price: float
    cost: float
    category: str
    stock: int

class CompetitorInfo(BaseModel):
    name: str
    price: float
    sales_volume: int
    rating: float

# --- Agent Input Models ---

class AnalysisRequest(BaseModel):
    product_ids: List[int]  # Updated to match Java (List<Long>)
    strategy_goal: str      # Updated to match Java
    constraints: str        # Updated to match Java
    task_id: int            # Added task_id (from Java DB)

# --- Agent Output Models ---

class DataAnalysisResult(BaseModel):
    product_id: str
    sales_trend: str = Field(..., description="销量趋势：上升/下降/平稳")
    inventory_status: str = Field(..., description="库存状态：积压/正常/紧缺")
    price_elasticity: float = Field(..., description="价格弹性系数")
    promotion_sensitivity: str = Field(..., description="促销敏感度：高/中/低")
    suggested_action: str = Field(..., description="建议动作：降价/维持/提价")
    confidence_score: float = Field(..., description="置信度 0-1")

class MarketIntelResult(BaseModel):
    product_id: str
    competitor_price_range: List[float] = Field(..., description="竞品价格区间 [min, max]")
    market_competition: str = Field(..., description="市场竞争强度：激烈/一般/蓝海")
    competitor_activities: List[str] = Field(..., description="竞品近期活动")
    customer_sentiment: str = Field(..., description="消费者情感倾向：正面/中性/负面")

class RiskControlResult(BaseModel):
    product_id: str
    min_price_limit: float = Field(..., description="最低限价")
    max_discount_rate: float = Field(..., description="最大折扣率")
    profit_margin_impact: str = Field(..., description="利润率影响分析")
    risk_level: str = Field(..., description="风险等级：高/中/低")
    compliance_check: bool = Field(..., description="合规性检查通过")

class FinalDecision(BaseModel):
    product_id: str
    product_name: str
    original_price: float
    suggested_price: float
    discount_rate: float
    decision_reason: str = Field(..., description="最终决策理由")
    analysis_summary: DataAnalysisResult
    market_summary: MarketIntelResult
    risk_summary: RiskControlResult
    execution_plan: List[str] = Field(..., description="执行计划步骤")

# --- API Response Models ---

class DecisionResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[FinalDecision] = None
    message: str = "Task started"
