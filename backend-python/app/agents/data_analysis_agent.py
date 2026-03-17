from typing import List, Dict, Any, Tuple, Optional
from app.schemas.decision import (
    AnalysisRequest, 
    DataAnalysisResult,
    ProductBase,
    SalesData
)
import logging

logger = logging.getLogger(__name__)

class DataAnalysisAgent:
    """
    DataAnalysisAgent（数据分析专家）
    
    核心职责：
    - 基于内部经营数据，提供客观的销量趋势和库存健康度分析
    - 分析销量趋势（7 天/30 天/90 天多周期）
    - 评估库存周转健康度
    - 估算价格弹性系数
    - 判断商品生命周期阶段
    - 检测异常数据（如刷单、系统故障）
    
    不负责：
    - 竞品价格对比（交给 MarketIntelAgent）
    - 利润计算（交给 RiskControlAgent）
    - 最终决策建议（交给 ManagerCoordinatorAgent）
    """

    # 类常量：配置参数
    CATEGORY_DEFAULT_ELASTICITY = {
        "数码": -1.5,
        "服装": -2.0,
        "食品": -1.2,
        "家居": -1.3,
        "美妆": -1.8,
        "default": -1.5
    }
    
    TARGET_TURNOVER_DAYS = {
        "数码": 30,
        "服装": 45,
        "食品": 15,
        "家居": 40,
        "美妆": 30,
        "default": 30
    }

    def __init__(self):
        """初始化 Agent"""
        pass

    def analyze(self, request: AnalysisRequest) -> DataAnalysisResult:
        """
        执行数据分析任务的主入口
        
        :param request: 包含商品、销量、竞品等全量信息的请求对象
        :return: DataAnalysisResult 结构化分析结果
        """
        try:
            product = request.product
            sales_data = request.sales_data
            
            # 1. 数据质量检查与异常检测
            anomalies = self._detect_data_anomalies(sales_data)
            
            # 2. 数据预处理（平滑异常值）
            cleaned_sales_7d = self._smooth_anomalies(sales_data.sales_history_7d)
            cleaned_sales_30d = self._smooth_anomalies(sales_data.sales_history_30d)
            cleaned_sales_90d = self._smooth_anomalies(sales_data.sales_history_90d)
            
            # 3. 多周期销量趋势分析（核心）
            sales_trend, trend_score, trend_details = self._analyze_sales_trend_comprehensive(
                cleaned_sales_7d,
                cleaned_sales_30d,
                cleaned_sales_90d
            )
            
            # 4. 库存健康度分析（多维度）
            (inventory_status, health_score, turnover_days, 
             inventory_details) = self._analyze_inventory_health_comprehensive(
                product, cleaned_sales_30d
            )
            
            # 5. 商品生命周期判断
            lifecycle_stage, lifecycle_evidence = self._determine_lifecycle_stage(
                product, sales_trend, health_score
            )
            
            # 6. 价格弹性估算
            elasticity, elasticity_confidence = self._estimate_demand_elasticity(
                product.category,
                sales_data.promotion_history,
                product.current_price,
                product.cost
            )
            
            # 7. 生成建议（基于规则 + 数据驱动）
            (recommended_action, discount_range, confidence, 
             reasons) = self._generate_recommendation_comprehensive(
                sales_trend, trend_score,
                inventory_status, health_score, turnover_days,
                lifecycle_stage,
                elasticity,
                product
            )
            recommended_action, discount_range, reasons = self._apply_constraint_guardrails(
                request,
                recommended_action,
                discount_range,
                reasons,
            )
            
            # 8. 计算数据质量评分
            data_quality_score = self._calculate_data_quality_score(
                sales_data, anomalies
            )
            
            # 9. 构造分析详情（可解释性）
            analysis_details = {
                "sales_trend_calculation": trend_details,
                "inventory_health_calculation": inventory_details,
                "lifecycle_analysis": {
                    "stage": lifecycle_stage,
                    "evidence": lifecycle_evidence
                },
                "elasticity_estimation": {
                    "coefficient": elasticity,
                    "confidence": elasticity_confidence
                }
            }
            
            # 10. 返回结构化结果
            return DataAnalysisResult(
                sales_trend=sales_trend,
                sales_trend_score=trend_score,
                inventory_status=inventory_status,
                inventory_health_score=health_score,
                estimated_turnover_days=int(turnover_days) if turnover_days < 999 else None,
                demand_elasticity=elasticity,
                demand_elasticity_confidence=elasticity_confidence,
                product_lifecycle_stage=lifecycle_stage,
                lifecycle_evidence=lifecycle_evidence,
                has_anomalies=len(anomalies) > 0,
                anomaly_list=anomalies,
                recommended_action=recommended_action,
                recommended_discount_range=discount_range,
                recommendation_confidence=confidence,
                recommendation_reasons=reasons,
                analysis_details=analysis_details,
                data_quality_score=data_quality_score,
                limitations=self._get_analysis_limitations(sales_data, product)
            )
            
        except Exception as e:
            logger.error(f"DataAnalysisAgent 分析失败：{e}", exc_info=True)
            # 返回降级结果
            return self._get_fallback_result(request)

    def _detect_data_anomalies(self, sales_data: SalesData) -> List[Dict[str, Any]]:
        """
        检测数据异常（如刷单、系统故障）
        """
        anomalies = []
        
        # 检测 7 天销量异常
        if sales_data.sales_history_7d and len(sales_data.sales_history_7d) >= 2:
            last_day = sales_data.sales_history_7d[-1]
            prev_days_avg = sum(sales_data.sales_history_7d[:-1]) / (len(sales_data.sales_history_7d) - 1)
            
            if prev_days_avg > 0 and last_day > prev_days_avg * 5:
                anomalies.append({
                    "type": "sales_spike",
                    "description": f"最近一日销量异常峰值 ({last_day})，是前几日平均值 ({prev_days_avg:.1f}) 的 5 倍以上，疑似刷单或系统故障",
                    "severity": "high",
                    "affected_field": "sales_history_7d"
                })
            
            # 检测零销量
            zero_days = sum(1 for s in sales_data.sales_history_7d if s == 0)
            if zero_days >= 3:
                anomalies.append({
                    "type": "zero_sales",
                    "description": f"最近 7 天中有{zero_days}天销量为 0，可能存在断货或流量问题",
                    "severity": "medium",
                    "affected_field": "sales_history_7d"
                })
        
        return anomalies

    def _smooth_anomalies(self, sales_data: List[int]) -> List[int]:
        """
        平滑异常值（使用移动平均）
        """
        if not sales_data or len(sales_data) < 3:
            return sales_data
        
        smoothed = sales_data.copy()
        avg = sum(sales_data) / len(sales_data)
        std = (sum((x - avg) ** 2 for x in sales_data) / len(sales_data)) ** 0.5
        
        for i, val in enumerate(smoothed):
            if abs(val - avg) > 3 * std:  # 3 倍标准差视为异常
                # 使用前后两天的平均值替代
                if i > 0 and i < len(smoothed) - 1:
                    smoothed[i] = (smoothed[i-1] + smoothed[i+1]) / 2
                elif i == 0:
                    smoothed[i] = smoothed[i+1]
                else:
                    smoothed[i] = smoothed[i-1]
        
        return smoothed

    def _analyze_sales_trend_comprehensive(
        self, 
        sales_7d: List[int],
        sales_30d: List[int],
        sales_90d: List[int]
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        多周期综合分析销量趋势
        
        :return: (趋势描述，趋势得分，详细计算过程)
        """
        # 短期趋势（7 天）权重 50%
        short_term_trend, short_score = self._calculate_trend_score(sales_7d)
        
        # 中期趋势（30 天）权重 30%
        mid_term_trend, mid_score = self._calculate_trend_score(sales_30d)
        
        # 长期趋势（90 天）权重 20%
        long_term_trend, long_score = self._calculate_trend_score(sales_90d)
        
        # 加权综合得分
        composite_score = (
            short_score * 0.5 + 
            mid_score * 0.3 + 
            long_score * 0.2
        )
        
        # 根据综合得分判断趋势
        if composite_score > 0.3:
            trend_label = "rapid_rising"
        elif composite_score > 0.1:
            trend_label = "rising"
        elif composite_score < -0.3:
            trend_label = "rapid_declining"
        elif composite_score < -0.1:
            trend_label = "declining"
        else:
            trend_label = "stable"
        
        # 详细计算过程（用于可解释性）
        trend_details = {
            "short_term_trend": short_score,
            "mid_term_trend": mid_score,
            "long_term_trend": long_score,
            "composite_score": composite_score,
            "formula": f"{short_score:.2f}*0.5 + {mid_score:.2f}*0.3 + {long_score:.2f}*0.2 = {composite_score:.2f}",
            "data_points": {
                "sales_7d": len(sales_7d),
                "sales_30d": len(sales_30d),
                "sales_90d": len(sales_90d)
            }
        }
        
        return trend_label, composite_score, trend_details

    def _calculate_trend_score(self, sales_data: List[int]) -> Tuple[str, float]:
        """
        计算单个周期的趋势得分
        
        :return: (趋势描述，得分 -1.0~1.0)
        """
        if not sales_data or len(sales_data) < 2:
            return "insufficient_data", 0.0
        
        # 使用线性回归斜率近似计算
        n = len(sales_data)
        mid = n // 2
        
        if mid == 0:
            mid = 1
        
        first_half_avg = sum(sales_data[:mid]) / mid
        second_half_avg = sum(sales_data[mid:]) / (n - mid) if n > mid else 0
        
        if first_half_avg == 0:
            change_rate = 1.0 if second_half_avg > 0 else 0.0
        else:
            change_rate = (second_half_avg - first_half_avg) / first_half_avg
        
        # 归一化到 -1.0~1.0
        normalized_score = max(-1.0, min(1.0, change_rate))
        
        if change_rate > 0.2:
            return "rising", normalized_score
        elif change_rate < -0.2:
            return "declining", normalized_score
        else:
            return "stable", normalized_score

    def _analyze_inventory_health_comprehensive(
        self,
        product: ProductBase,
        sales_30d: List[int]
    ) -> Tuple[str, float, float, Dict[str, Any]]:
        """
        综合多维度分析库存健康度
        
        :return: (库存状态，健康度得分，周转天数，详细计算过程)
        """
        # 计算日均销量
        if not sales_30d or len(sales_30d) == 0:
            avg_daily_sales = 0.0
        else:
            avg_daily_sales = sum(sales_30d) / len(sales_30d)
        
        # 维度 1：周转天数
        if avg_daily_sales == 0:
            turnover_days = 999.0  # 滞销
        else:
            turnover_days = product.stock / avg_daily_sales
        
        # 获取类目目标周转天数
        target_turnover = self.TARGET_TURNOVER_DAYS.get(
            product.category[:2], 
            self.TARGET_TURNOVER_DAYS["default"]
        )
        
        # 维度 2：库龄惩罚
        stock_age_days = product.stock_age_days or 0
        if stock_age_days > 180:
            stock_age_penalty = -30
        elif stock_age_days > 90:
            stock_age_penalty = -15
        elif stock_age_days > 60:
            stock_age_penalty = -5
        else:
            stock_age_penalty = 0
        
        # 维度 3：季节匹配度
        if product.is_seasonal:
            # TODO: 实现季节判断逻辑
            season_penalty = 0  # 暂时不扣分
        else:
            season_penalty = 0
        
        # 综合健康度评分（基准 100 分）
        turnover_penalty = -abs(turnover_days - target_turnover) * 0.5
        health_score = max(0, min(100, 100 + turnover_penalty + stock_age_penalty + season_penalty))
        
        # 根据健康度得分判断状态
        if health_score < 30:
            inventory_status = "severe_overstock"
        elif health_score < 50:
            inventory_status = "overstock"
        elif health_score < 80:
            inventory_status = "normal"
        elif health_score < 95:
            inventory_status = "tight"
        else:
            inventory_status = "shortage"
        
        # 详细计算过程
        inventory_details = {
            "turnover_days": turnover_days,
            "target_turnover_days": target_turnover,
            "turnover_penalty": turnover_penalty,
            "stock_age_days": stock_age_days,
            "stock_age_penalty": stock_age_penalty,
            "season_penalty": season_penalty,
            "formula": f"100 + ({turnover_penalty:.1f}) + ({stock_age_penalty}) + ({season_penalty}) = {health_score:.1f}"
        }
        
        return inventory_status, health_score, turnover_days, inventory_details

    def _determine_lifecycle_stage(
        self,
        product: ProductBase,
        sales_trend: str,
        inventory_health: float
    ) -> Tuple[str, str]:
        """
        判断商品生命周期阶段
        """
        # 如果已有明确的生命周期标记，直接使用
        if product.product_lifecycle_stage:
            return product.product_lifecycle_stage, f"使用预设值：{product.product_lifecycle_stage}"
        
        # 基于规则推断
        evidence = []
        
        if product.is_new_product:
            stage = "introduction"
            evidence.append("新品（<30 天）")
        elif sales_trend in ["rapid_rising", "rising"]:
            stage = "growth"
            evidence.append(f"销量快速增长（趋势：{sales_trend}）")
        elif sales_trend == "stable" and inventory_health > 60:
            stage = "maturity"
            evidence.append(f"销量稳定且库存健康（健康度：{inventory_health:.1f}）")
        elif sales_trend in ["declining", "rapid_declining"]:
            stage = "decline"
            evidence.append(f"销量下滑（趋势：{sales_trend}）")
        else:
            stage = "maturity"
            evidence.append("默认判断为成熟期")
        
        return stage, "；".join(evidence)

    def _estimate_demand_elasticity(
        self,
        category: str,
        promotion_history: List[Dict[str, Any]],
        current_price: float,
        cost: float
    ) -> Tuple[float, float]:
        """
        估算价格弹性系数
        
        :return: (弹性系数，置信度)
        """
        # 如果有足够的促销历史数据，使用数据估算
        if len(promotion_history) >= 3:
            elasticities = []
            
            for promo in promotion_history:
                discount_price = promo.get('discount_price', current_price)
                sales_before = promo.get('sales_before', 0)
                sales_during = promo.get('sales_during', 0)
                
                if sales_before > 0 and discount_price < current_price:
                    price_change_pct = (discount_price - current_price) / current_price
                    sales_change_pct = (sales_during - sales_before) / sales_before
                    
                    if price_change_pct != 0:
                        elasticity = sales_change_pct / price_change_pct
                        elasticities.append(elasticity)
            
            if elasticities:
                avg_elasticity = sum(elasticities) / len(elasticities)
                confidence = min(0.9, 0.5 + len(elasticities) * 0.1)
                return avg_elasticity, confidence
        
        # 数据不足，使用类目默认值
        default_elasticity = self.CATEGORY_DEFAULT_ELASTICITY.get(
            category[:2], 
            self.CATEGORY_DEFAULT_ELASTICITY["default"]
        )
        
        return default_elasticity, 0.3

    def _generate_recommendation_comprehensive(
        self,
        sales_trend: str,
        trend_score: float,
        inventory_status: str,
        health_score: float,
        turnover_days: float,
        lifecycle_stage: str,
        elasticity: float,
        product: ProductBase
    ) -> Tuple[str, Tuple[float, float], float, List[str]]:
        """
        综合分析生成建议
        
        :return: (建议操作，折扣区间，置信度，理由列表)
        """
        reasons = []
        confidence = 0.8
        min_discount = 1.0
        max_discount = 1.0
        recommended_action = "maintain"
        
        # 策略 1：基于库存状态
        if inventory_status in ["severe_overstock", "overstock"]:
            if turnover_days > 120:
                # 严重积压，建议清仓
                min_discount = 0.6
                max_discount = 0.75
                recommended_action = "clearance"
                reasons.append(f"库存严重积压（周转{turnover_days:.0f}天），建议清仓处理")
            elif turnover_days > 60:
                # 中度积压，建议打折
                min_discount = 0.75
                max_discount = 0.9
                recommended_action = "discount"
                reasons.append(f"库存存在积压风险（周转{turnover_days:.0f}天），建议适度打折")
        
        # 策略 2：基于销量趋势
        if sales_trend in ["declining", "rapid_declining"]:
            if recommended_action == "maintain":
                min_discount = 0.85
                max_discount = 0.95
                recommended_action = "discount"
            reasons.append(f"销量呈下降趋势（得分：{trend_score:.2f}），需通过促销刺激")
        
        # 策略 3：基于生命周期
        if lifecycle_stage == "decline":
            if recommended_action != "clearance":
                min_discount = min(min_discount, 0.8)
                max_discount = min(max_discount, 0.9)
                recommended_action = "discount"
            reasons.append("商品处于衰退期，建议尽快回笼资金")
        
        # 策略 4：库存紧缺时不打折
        if inventory_status in ["tight", "shortage"]:
            min_discount = 1.0
            max_discount = 1.0
            recommended_action = "maintain"
            reasons = ["库存紧张，不建议打折，需尽快补货"]
        
        # 策略 5：成本底线检查
        if product.cost > 0:
            break_even_discount = product.cost / product.current_price
            if min_discount < break_even_discount:
                min_discount = break_even_discount
                reasons.append(f"折扣受成本限制（最低{break_even_discount:.0%}折保本）")
                confidence *= 0.7
        
        # 确保折扣区间合理
        min_discount = max(0.5, min(min_discount, 1.0))
        max_discount = max(min_discount, min(max_discount, 1.0))
        
        return recommended_action, (min_discount, max_discount), confidence, reasons

    def _apply_constraint_guardrails(
        self,
        request: AnalysisRequest,
        recommended_action: str,
        discount_range: Tuple[float, float],
        reasons: List[str],
    ) -> Tuple[str, Tuple[float, float], List[str]]:
        risk_data = request.risk_data
        product = request.product
        min_allowed_price = risk_data.price_floor or 0.0

        if risk_data.min_profit_markup is not None:
            min_allowed_price = max(min_allowed_price, product.cost * (1 + risk_data.min_profit_markup))

        if min_allowed_price and product.current_price + 1e-6 < min_allowed_price:
            reasons.append(f"当前售价已低于约束底线 {min_allowed_price:.2f} 元，数据分析不支持进一步降价")
            return "maintain", (1.0, 1.0), reasons

        min_rate, max_rate = discount_range
        if risk_data.max_discount_allowed is not None and min_rate < risk_data.max_discount_allowed:
            min_rate = max(min_rate, risk_data.max_discount_allowed)
            max_rate = max(min_rate, max_rate)
            reasons.append(f"折扣建议已按约束收敛，最低价格系数上调到 {min_rate:.2f}")

        if min_rate >= 0.999:
            return "maintain", (1.0, 1.0), reasons

        return recommended_action, (min_rate, max_rate), reasons

    def _calculate_data_quality_score(
        self,
        sales_data: SalesData,
        anomalies: List[Dict[str, Any]]
    ) -> float:
        """
        计算数据质量评分（0~1）
        """
        score = 1.0
        
        # 扣分项 1：数据完整性
        if not sales_data.sales_history_7d:
            score -= 0.3
        if not sales_data.sales_history_30d:
            score -= 0.2
        if not sales_data.sales_history_90d:
            score -= 0.1
        
        # 扣分项 2：异常数据
        high_severity_count = sum(1 for a in anomalies if a.get('severity') == 'high')
        medium_severity_count = sum(1 for a in anomalies if a.get('severity') == 'medium')
        
        score -= high_severity_count * 0.2
        score -= medium_severity_count * 0.1
        
        return max(0.0, min(1.0, score))

    def _get_analysis_limitations(
        self,
        sales_data: SalesData,
        product: ProductBase
    ) -> List[str]:
        """
        返回分析局限性说明
        """
        limitations = []
        
        if not sales_data.sales_history_90d:
            limitations.append("缺少 90 天长期销量数据，趋势判断可能不够准确")
        
        if not sales_data.promotion_history:
            limitations.append("缺少历史促销数据，价格弹性估算使用类目默认值")
        
        if product.is_new_product:
            limitations.append("新品历史数据有限，分析结果仅供参考")
        
        if not sales_data.pv_7d or not sales_data.uv_7d:
            limitations.append("缺少流量数据，无法分析转化率变化")
        
        return limitations

    def _get_fallback_result(self, request: AnalysisRequest) -> DataAnalysisResult:
        """
        返回降级结果（当分析失败时）
        """
        return DataAnalysisResult(
            sales_trend="stable",
            sales_trend_score=0.0,
            inventory_status="normal",
            inventory_health_score=50.0,
            estimated_turnover_days=None,
            demand_elasticity=None,
            demand_elasticity_confidence=None,
            product_lifecycle_stage="maturity",
            lifecycle_evidence="分析失败，使用默认值",
            has_anomalies=False,
            anomaly_list=[],
            recommended_action="maintain",
            recommended_discount_range=(1.0, 1.0),
            recommendation_confidence=0.3,
            recommendation_reasons=["数据分析失败，建议人工介入"],
            analysis_details={"error": "分析过程中发生错误"},
            data_quality_score=0.0,
            limitations=["分析失败，结果不可靠"]
        )
