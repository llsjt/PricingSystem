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


def _normalize_input(raw: Any) -> dict:
    """将 CrewAI 传入的工具参数归一化为 dict。
    CrewAI 可能传 dict（已解析的 JSON）或 str（JSON 字符串），
    此函数统一处理两种情况。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {}


# ── 商品数据汇总工具 ─────────────────────────────────────────
@tool("汇总商品经营数据")
def summarize_product_data(input_json: Any) -> str:
    """
    根据商品上下文、每日销售指标和流量数据，汇总商品近30天经营概况。
    输入JSON字段:
      - product: 商品上下文 (productId, shopId, productName, categoryName, currentPrice, costPrice, stock)
      - metrics: 每日指标列表 (statDate, visitorCount, addCartCount, payBuyerCount, salesCount, turnover, conversionRate)
      - traffic: 流量数据列表 (statDate, trafficSource, impressionCount, clickCount, visitorCount, payAmount, roi)
    返回: 月销量、月营业额、平均转化率、总访客数、CTR 等汇总数据
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    # 从字典重建 Pydantic 模型
    product = ProductContext(**params.get("product", {}))
    metrics = [DailyMetricSnapshot(**m) for m in params.get("metrics", [])]
    traffic = [TrafficSnapshot(**t) for t in params.get("traffic", [])]

    # 调用底层工具计算
    result = _product_data_tool.summarize(product=product, metrics=metrics, traffic=traffic)
    return json.dumps(result, ensure_ascii=False, default=_default_serializer)


# ── 异常值清洗工具 ─────────────────────────────────────────
@tool("清洗销量异常值")
def clean_outliers(input_json: Any) -> str:
    """
    对销量序列执行 Winsorization（缩尾处理），去除极端值干扰。
    输入JSON字段:
      - values: 数值列表，例如每日销量 [10, 12, 8, 100, 11, ...]
    返回: 清洗后的数值列表
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    values = params.get("values", [])
    cleaned = _outlier_clean_tool.winsorize(values)
    return json.dumps({"cleaned_values": cleaned}, ensure_ascii=False)


# ── 价格弹性预估销量工具 ───────────────────────────────────
@tool("预估调价后销量")
def estimate_sales_volume(input_json: Any) -> str:
    """
    基于价格弹性模型，预估调价后的月销量。
    输入JSON字段:
      - baseline_sales: 基线月销量（整数）
      - current_price: 当前售价
      - target_price: 目标价格
      - strategy_goal: 策略目标 (MAX_PROFIT / MARKET_SHARE / CLEARANCE)
    返回: estimated_sales（预估月销量）
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    estimated = _elasticity_tool.estimate_sales(
        baseline_sales=int(params.get("baseline_sales", 30)),
        current_price=Decimal(str(params.get("current_price", 0))),
        target_price=Decimal(str(params.get("target_price", 0))),
        strategy_goal=str(params.get("strategy_goal", "")),
    )
    return json.dumps({"estimated_sales": estimated}, ensure_ascii=False)


# ── 利润预估工具 ─────────────────────────────────────────
@tool("预估利润")
def estimate_profit(input_json: Any) -> str:
    """
    根据价格、成本和预期销量，计算预估月利润。
    输入JSON字段:
      - price: 售价
      - cost_price: 成本价
      - expected_sales: 预期月销量（整数）
    返回: estimated_profit（预估月利润）
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    profit = _elasticity_tool.estimate_profit(
        price=Decimal(str(params.get("price", 0))),
        cost_price=Decimal(str(params.get("cost_price", 0))),
        expected_sales=int(params.get("expected_sales", 0)),
    )
    return json.dumps({"estimated_profit": str(profit)}, ensure_ascii=False)


# ── 风控规则评估工具 ─────────────────────────────────────
@tool("评估风控规则")
def evaluate_risk_rules(input_json: Any) -> str:
    """
    对候选价格执行硬约束校验：成本底线、最低利润率、价格上下限、最大折扣率。
    输入JSON字段:
      - current_price: 当前售价
      - cost_price: 成本价
      - candidate_price: 候选价格（待校验）
      - constraints: 约束条件字典，可包含:
          min_profit_rate(最低利润率,默认0.15), min_price, max_price, max_discount_rate
    返回: is_pass(是否通过), safe_floor_price(安全底价), suggested_price(风控建议价),
          risk_level(LOW/HIGH), need_manual_review(是否需人工复核)
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    result = _risk_rule_tool.evaluate(
        current_price=Decimal(str(params.get("current_price", 0))),
        cost_price=Decimal(str(params.get("cost_price", 0))),
        candidate_price=Decimal(str(params.get("candidate_price", 0))),
        constraints=params.get("constraints", {}),
    )
    return json.dumps(result, ensure_ascii=False, default=_default_serializer)


# ── 竞品数据查询工具（模拟数据） ──────────────────────────
@tool("查询竞品价格数据")
def search_competitors(input_json: Any) -> str:
    """
    获取竞品价格数据（模拟数据，非真实爬虫）。
    输入JSON字段:
      - product_id: 商品ID
      - product_title: 商品名称
      - category_name: 品类名称
      - current_price: 当前售价
    返回: 竞品列表，每条包含 competitorName, price, originalPrice, salesVolumeHint,
          promotionTag, shopType, sourcePlatform
    """
    params = _normalize_input(input_json)
    if not params:
        return json.dumps({"error": "输入参数无效"}, ensure_ascii=False)

    competitors = _competitor_service.get_competitors(
        product_id=int(params.get("product_id", 0)),
        product_title=params.get("product_title"),
        category_name=params.get("category_name"),
        current_price=Decimal(str(params.get("current_price", 0))),
    )
    return json.dumps({"competitors": competitors}, ensure_ascii=False, default=_default_serializer)
