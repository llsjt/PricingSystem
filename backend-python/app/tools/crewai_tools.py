"""
CrewAI @tool 包装层
===================
将已有的纯 Python 工具类包装为 CrewAI @tool 装饰器函数，
使 LLM Agent 能通过 function calling 调用这些工具。

每个 @tool 函数：
- 接收工具参数（CrewAI 可能传 dict 或 JSON 字符串）
- 内部调用原有工具类的方法
- 返回 JSON 字符串结果供 LLM 继续推理
"""

import json
from decimal import Decimal
from typing import Any

from crewai.tools import tool


from app.schemas.agent import DailyMetricSnapshot, ProductContext, TrafficSnapshot
from app.services.competitor_service import CompetitorService
from app.tools.elasticity_profit_tool import ElasticityProfitTool
from app.tools.outlier_clean_tool import OutlierCleanTool
from app.tools.product_data_tool import ProductDataTool
from app.tools.risk_rule_tool import RiskRuleTool

# ── 实例化底层工具（无状态，可全局复用） ──────────────────────
_product_data_tool = ProductDataTool()
_outlier_clean_tool = OutlierCleanTool()
_elasticity_tool = ElasticityProfitTool()
_risk_rule_tool = RiskRuleTool()
_competitor_service = CompetitorService()


def _default_serializer(obj: Any) -> Any:
    """JSON 序列化兜底：Decimal → str，其他转 str"""
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)



# ── 商品数据汇总工具 ─────────────────────────────────────────
@tool("汇总商品经营数据")
def summarize_product_data(product_json: str, metrics_json: str, traffic_json: str) -> str:
    """
    根据商品上下文、每日销售指标和流量数据，汇总商品近30天经营概况。
    参数:
      - product_json: 商品上下文JSON字符串 (productId, shopId, productName, categoryName, currentPrice, costPrice, stock)
      - metrics_json: 每日指标JSON数组字符串 (statDate, visitorCount, addCartCount, payBuyerCount, salesCount, turnover, conversionRate)
      - traffic_json: 流量数据JSON数组字符串 (statDate, trafficSource, impressionCount, clickCount, visitorCount, payAmount, roi)
    返回: 月销量、月营业额、平均转化率、总访客数、CTR 等汇总数据
    """
    product_data = json.loads(product_json) if isinstance(product_json, str) else product_json
    metrics_data = json.loads(metrics_json) if isinstance(metrics_json, str) else metrics_json
    traffic_data = json.loads(traffic_json) if isinstance(traffic_json, str) else traffic_json

    product = ProductContext(**product_data)
    metrics = [DailyMetricSnapshot(**m) for m in metrics_data]
    traffic = [TrafficSnapshot(**t) for t in traffic_data]

    result = _product_data_tool.summarize(product=product, metrics=metrics, traffic=traffic)
    return json.dumps(result, ensure_ascii=False, default=_default_serializer)


# ── 异常值清洗工具 ─────────────────────────────────────────
@tool("清洗销量异常值")
def clean_outliers(values: str) -> str:
    """
    对销量序列执行 Winsorization（缩尾处理），去除极端值干扰。
    参数:
      - values: JSON数组字符串，例如每日销量 "[10, 12, 8, 100, 11]"
    返回: 清洗后的数值列表
    """
    parsed = json.loads(values) if isinstance(values, str) else values
    cleaned = _outlier_clean_tool.winsorize(parsed)
    return json.dumps({"cleaned_values": cleaned}, ensure_ascii=False)


# ── 价格弹性预估销量工具 ───────────────────────────────────
@tool("预估调价后销量")
def estimate_sales_volume(
    baseline_sales: int,
    current_price: float,
    target_price: float,
    strategy_goal: str,
) -> str:
    """
    基于价格弹性模型，预估调价后的月销量。
    参数:
      - baseline_sales: 基线月销量（整数）
      - current_price: 当前售价
      - target_price: 目标价格
      - strategy_goal: 策略目标 (MAX_PROFIT / MARKET_SHARE / CLEARANCE)
    返回: estimated_sales（预估月销量）
    """
    estimated = _elasticity_tool.estimate_sales(
        baseline_sales=int(baseline_sales),
        current_price=Decimal(str(current_price)),
        target_price=Decimal(str(target_price)),
        strategy_goal=str(strategy_goal),
    )
    return json.dumps({"estimated_sales": estimated}, ensure_ascii=False)


# ── 利润预估工具 ─────────────────────────────────────────
@tool("预估利润")
def estimate_profit(
    price: float,
    cost_price: float,
    expected_sales: int,
) -> str:
    """
    根据价格、成本和预期销量，计算预估月利润。
    参数:
      - price: 售价
      - cost_price: 成本价
      - expected_sales: 预期月销量（整数）
    返回: estimated_profit（预估月利润）
    """
    profit = _elasticity_tool.estimate_profit(
        price=Decimal(str(price)),
        cost_price=Decimal(str(cost_price)),
        expected_sales=int(expected_sales),
    )
    return json.dumps({"estimated_profit": str(profit)}, ensure_ascii=False)


# ── 风控规则评估工具 ─────────────────────────────────────
@tool("评估风控规则")
def evaluate_risk_rules(
    current_price: float,
    cost_price: float,
    candidate_price: float,
    min_profit_rate: float = 0.15,
    max_discount_rate: float = 0.5,
    min_price: float = 0.0,
    max_price: float = 0.0,
) -> str:
    """
    对候选价格执行硬约束校验：成本底线、最低利润率、最大折扣率。
    参数:
      - current_price: 当前售价
      - cost_price: 成本价
      - candidate_price: 候选价格（待校验）
      - min_profit_rate: 最低利润率（默认0.15）
      - max_discount_rate: 最大折扣率（默认0.5）
      - min_price: 最低售价限制（0表示不限制）
      - max_price: 最高售价限制（0表示不限制）
    返回: is_pass(是否通过), safe_floor_price(安全底价), suggested_price(风控建议价),
          risk_level(LOW/HIGH), need_manual_review(是否需人工复核)
    """
    constraints: dict[str, Any] = {
        "min_profit_rate": min_profit_rate,
        "max_discount_rate": max_discount_rate,
    }
    if min_price > 0:
        constraints["min_price"] = min_price
    if max_price > 0:
        constraints["max_price"] = max_price
    result = _risk_rule_tool.evaluate(
        current_price=Decimal(str(current_price)),
        cost_price=Decimal(str(cost_price)),
        candidate_price=Decimal(str(candidate_price)),
        constraints=constraints,
    )
    return json.dumps(result, ensure_ascii=False, default=_default_serializer)


# ── 竞品数据查询工具（模拟数据） ──────────────────────────
@tool("查询竞品价格数据")
def search_competitors(
    product_id: int,
    product_title: str,
    category_name: str,
    current_price: float,
) -> str:
    """
    获取竞品价格数据（模拟数据，非真实爬虫）。
    参数:
      - product_id: 商品ID
      - product_title: 商品名称
      - category_name: 品类名称
      - current_price: 当前售价
    返回: 竞品列表，每条包含 competitorName, price, originalPrice, salesVolumeHint,
          promotionTag, shopType, sourcePlatform
    """
    competitors = _competitor_service.get_competitors(
        product_id=int(product_id),
        product_title=product_title,
        category_name=category_name,
        current_price=Decimal(str(current_price)),
    )
    return json.dumps({"competitors": competitors}, ensure_ascii=False, default=_default_serializer)
