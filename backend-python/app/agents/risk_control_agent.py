from typing import List, Dict, Any, Tuple, Optional
from app.schemas.decision import (
    AnalysisRequest, 
    RiskControlResult,
    ProductBase,
    RiskData
)
import logging

logger = logging.getLogger(__name__)

class RiskControlAgent:
    """
    RiskControlAgent（风险控制总监）
    
    核心职责：
    - 财务底线守护者，拥有一票否决权
    - 毛利率计算与监控
    - 最低价格红线设定
    - 亏损风险评估
    - 现金流风险分析
    - 库存贬值风险评估
    - 合规性检查（如价格欺诈）
    
    不负责：
    - 销量预测（交给 DataAnalysisAgent）
    - 市场竞争分析（交给 MarketIntelAgent）
    """

    # 类常量：风险权重配置
    RISK_WEIGHTS = {
        'profit_risk': 0.40,      # 利润风险权重 40%
        'inventory_risk': 0.25,   # 库存风险权重 25%
        'cash_flow_risk': 0.20,   # 现金流风险权重 20%
        'compliance_risk': 0.15   # 合规风险权重 15%
    }
    
    # 类目默认毛利率要求
    CATEGORY_MIN_MARGIN = {
        "数码": 0.15,
        "服装": 0.30,
        "食品": 0.20,
        "家居": 0.25,
        "美妆": 0.35,
        "default": 0.20
    }

    def __init__(self):
        """初始化 Agent"""
        pass

    def analyze(self, request: AnalysisRequest) -> RiskControlResult:
        """
        执行风险控制分析任务的主入口
        
        :param request: 包含商品、销量、成本等全量信息的请求对象
        :return: RiskControlResult 结构化分析结果
        """
        try:
            product = request.product
            risk_data = request.risk_data
            
            # 1. 成本结构分析（全成本核算）
            total_cost, cost_breakdown = self._calculate_total_cost_comprehensive(
                product.cost,
                product.current_price,
                risk_data.cost_breakdown
            )
            
            # 2. 当前毛利率计算（多维度）
            current_margin, margin_details = self._calculate_profit_margin_comprehensive(
                product.current_price,
                total_cost
            )
            
            # 3. 价格红线计算（盈亏平衡点 + 最低利润）
            (break_even_price, min_safe_price, absolute_floor, 
             price_details) = self._calculate_price_red_lines(
                total_cost,
                product.current_price,
                risk_data.min_profit_margin,
                risk_data.price_floor,
                risk_data.is_brand_controlled
            )

            required_min_price, current_price_compliant, constraint_summary = self._calculate_required_min_price(
                product,
                total_cost,
                risk_data,
                break_even_price,
                min_safe_price,
                absolute_floor,
            )
             
            # 4. 最大安全折扣计算
            max_safe_discount, discount_conditions = self._calculate_max_safe_discount(
                product.current_price,
                required_min_price,
                break_even_price,
                risk_data.max_discount_allowed
            )
            
            # 5. 综合风险评估（4 个维度）
            (risk_level, risk_score, risk_breakdown, 
             risk_details) = self._assess_risk_level_comprehensive(
                current_margin,
                risk_data.min_profit_margin,
                product.stock,
                product.stock_age_days,
                risk_data.refund_rate,
                risk_data.complaint_rate,
                risk_data.cash_conversion_cycle
            )
            
            # 6. 促销审批（一票否决权）
            allow_promotion, veto_reason, conditions = self._check_promotion_feasibility_comprehensive(
                risk_level,
                current_price_compliant,
                break_even_price,
                required_min_price,
                absolute_floor,
                product.current_price,
            )
            
            # 7. 计算折后毛利率
            margin_after_discount = self._calculate_profit_margin(
                product.current_price * max_safe_discount,
                total_cost
            ) if allow_promotion else current_margin
            
            # 8. 生成风险预警
            warnings = self._generate_risk_warnings(
                risk_level,
                current_margin,
                risk_data,
                product,
                current_price_compliant,
                required_min_price,
            )
             
            # 9. 生成建议
            recommendation, reasons = self._generate_recommendation(
                allow_promotion,
                risk_level,
                current_margin,
                risk_data.min_profit_margin,
                current_price_compliant,
                required_min_price,
                product.current_price,
            )
            
            # 10. 构造计算详情（可解释性）
            calculation_details = {
                "cost_breakdown": cost_breakdown,
                "margin_calculation": margin_details,
                "price_red_lines": price_details,
                "constraint_summary": constraint_summary,
                "risk_assessment": risk_details,
                "veto_check": {
                    "allow_promotion": allow_promotion,
                    "veto_reason": veto_reason
                }
            }
            
            # 11. 合规检查
            compliance_check, compliance_issues = self._check_compliance(
                product.current_price,
                product.original_price,
                max_safe_discount
            )
            
            # 12. 返回结构化结果
            return RiskControlResult(
                current_profit_margin=current_margin,
                profit_margin_after_discount=margin_after_discount,
                break_even_price=break_even_price,
                min_safe_price=min_safe_price,
                required_min_price=required_min_price,
                absolute_price_floor=absolute_floor,
                current_price_compliant=current_price_compliant,
                risk_level=risk_level,
                risk_score=risk_score,
                risk_breakdown=risk_breakdown,
                allow_promotion=allow_promotion,
                max_safe_discount=max_safe_discount,
                discount_conditions=conditions,
                warnings=warnings,
                recommendation=recommendation,
                recommendation_reasons=reasons,
                constraint_summary=constraint_summary,
                calculation_details=calculation_details,
                compliance_check=compliance_check,
                veto_reason=veto_reason if not allow_promotion else None
            )
            
        except Exception as e:
            logger.error(f"RiskControlAgent 分析失败：{e}", exc_info=True)
            # 返回降级结果（保守策略）
            return self._get_fallback_result(request)

    def _calculate_total_cost_comprehensive(
        self,
        cost: float,
        current_price: float,
        cost_breakdown: Optional[Dict[str, float]]
    ) -> Tuple[float, Dict[str, float]]:
        """
        综合全成本核算
        
        :return: (总成本，成本明细)
        """
        if cost_breakdown:
            # 使用详细成本明细
            total = sum(cost_breakdown.values())
            breakdown = cost_breakdown
        else:
            # 简化估算：成本 = 采购成本 + 运营费用（按 20% 估算）
            procurement_cost = cost
            operating_cost = cost * 0.20  # 运营费用（仓储、人工、物流等）
            platform_commission = current_price * 0.05  # 平台扣点 5%
            
            total = procurement_cost + operating_cost + platform_commission
            breakdown = {
                "procurement_cost": procurement_cost,
                "operating_cost": operating_cost,
                "platform_commission": platform_commission,
                "total": total
            }
        
        return total, breakdown

    def _calculate_profit_margin_comprehensive(
        self,
        price: float,
        total_cost: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        综合毛利率计算
        
        :return: (毛利率，计算详情)
        """
        if price <= 0:
            return -1.0, {"error": "价格为 0 或负数"}
        
        profit = price - total_cost
        margin = profit / price
        
        details = {
            "selling_price": price,
            "total_cost": total_cost,
            "profit": profit,
            "margin": margin,
            "formula": f"({price} - {total_cost}) / {price} = {margin:.2%}"
        }
        
        return margin, details

    def _calculate_profit_margin(self, price: float, cost: float) -> float:
        """简化毛利率计算"""
        if price <= 0:
            return -1.0
        return (price - cost) / price

    def _calculate_price_red_lines(
        self,
        total_cost: float,
        current_price: float,
        min_margin: float,
        price_floor: Optional[float],
        is_brand_controlled: bool
    ) -> Tuple[float, float, Optional[float], Dict[str, Any]]:
        """
        计算价格红线（盈亏平衡点、最低安全价、绝对底线）
        
        :return: (盈亏平衡价，最低安全价，绝对底线，详情)
        """
        # 1. 盈亏平衡价（不亏不赚）
        break_even_price = total_cost
        
        # 2. 最低安全价（含目标利润）
        if min_margin < 1.0:
            min_safe_price = total_cost / (1 - min_margin)
        else:
            min_safe_price = total_cost * (1 + min_margin)
        
        # 3. 绝对底线（品牌方限价或其他硬性约束）
        absolute_floor = price_floor if is_brand_controlled and price_floor else None
        
        # 详细计算
        price_details = {
            "total_cost": total_cost,
            "break_even_price": break_even_price,
            "min_safe_price": min_safe_price,
            "absolute_floor": absolute_floor,
            "min_margin_requirement": min_margin,
            "is_brand_controlled": is_brand_controlled,
            "formulas": {
                "break_even": f"总成本 = {total_cost}",
                "min_safe": f"总成本 / (1 - 最低利润率) = {total_cost} / (1 - {min_margin}) = {min_safe_price:.2f}"
            }
        }
        
        return break_even_price, min_safe_price, absolute_floor, price_details

    def _calculate_max_safe_discount(
        self,
        current_price: float,
        min_safe_price: float,
        break_even_price: float,
        max_discount_allowed: Optional[float]
    ) -> Tuple[float, List[str]]:
        """
        计算最大安全折扣
        
        :return: (最大安全折扣，附加条件)
        """
        conditions = []
        
        # 1. 基于最低安全价计算
        if current_price > 0:
            max_discount = min_safe_price / current_price
        else:
            max_discount = 1.0
        
        # 2. 检查是否超过盈亏平衡点
        if max_discount < (break_even_price / current_price if current_price > 0 else 1.0):
            conditions.append("警告：折扣已接近盈亏平衡点")
        
        # 3. 考虑外部约束（如品牌方最大允许折扣）
        if max_discount_allowed and max_discount_allowed < max_discount:
            max_discount = max_discount_allowed
            conditions.append(f"受外部约束限制，最大折扣调整为{max_discount_allowed:.0%}")
        
        # 4. 确保折扣不低于 50%（防止极端情况）
        max_discount = max(0.5, min(1.0, max_discount))
        
        # 保留两位小数
        max_discount = int(max_discount * 100) / 100.0
        
        return max_discount, conditions

    def _calculate_required_min_price(
        self,
        product: ProductBase,
        total_cost: float,
        risk_data: RiskData,
        break_even_price: float,
        min_safe_price: float,
        absolute_floor: Optional[float],
    ) -> Tuple[float, bool, List[str]]:
        required_min_price = max(break_even_price, min_safe_price)
        summary = list(risk_data.constraint_summary or [])

        if risk_data.min_profit_markup is not None:
            markup_price = product.cost * (1 + risk_data.min_profit_markup)
            required_min_price = max(required_min_price, markup_price)
            summary.append(f"按成本口径测算，最低执行价格需达到 {markup_price:.2f} 元")

        if absolute_floor is not None:
            required_min_price = max(required_min_price, absolute_floor)
            summary.append(f"价格底线约束要求售价不低于 {absolute_floor:.2f} 元")

        if risk_data.price_ceiling is not None:
            summary.append(f"价格上限约束要求售价不高于 {risk_data.price_ceiling:.2f} 元")

        required_min_price = round(required_min_price, 2)
        current_price_compliant = product.current_price + 1e-6 >= required_min_price
        return required_min_price, current_price_compliant, self._dedupe_messages(summary)

    def _assess_risk_level_comprehensive(
        self,
        current_margin: float,
        min_margin: float,
        stock: int,
        stock_age_days: Optional[int],
        refund_rate: float,
        complaint_rate: float,
        cash_conversion_cycle: Optional[int]
    ) -> Tuple[str, float, Dict[str, float], Dict[str, Any]]:
        """
        综合 4 个维度评估风险等级
        
        :return: (风险等级，风险得分，风险明细，详情)
        """
        risk_breakdown = {}
        
        # 维度 1：利润风险（权重 40%）
        profit_risk = self._assess_profit_risk(current_margin, min_margin)
        risk_breakdown['profit_risk'] = profit_risk
        
        # 维度 2：库存风险（权重 25%）
        inventory_risk = self._assess_inventory_risk(stock, stock_age_days)
        risk_breakdown['inventory_risk'] = inventory_risk
        
        # 维度 3：现金流风险（权重 20%）
        cash_flow_risk = self._assess_cash_flow_risk(cash_conversion_cycle)
        risk_breakdown['cash_flow_risk'] = cash_flow_risk
        
        # 维度 4：合规风险（权重 15%）
        compliance_risk = self._assess_compliance_risk(refund_rate, complaint_rate)
        risk_breakdown['compliance_risk'] = compliance_risk
        
        # 加权综合得分
        total_score = (
            profit_risk * self.RISK_WEIGHTS['profit_risk'] +
            inventory_risk * self.RISK_WEIGHTS['inventory_risk'] +
            cash_flow_risk * self.RISK_WEIGHTS['cash_flow_risk'] +
            compliance_risk * self.RISK_WEIGHTS['compliance_risk']
        )
        
        # 判断风险等级
        if total_score >= 70:
            risk_level = "high"
            level_label = "高"
        elif total_score >= 40:
            risk_level = "medium"
            level_label = "中"
        else:
            risk_level = "low"
            level_label = "低"
        
        # 详细计算
        risk_details = {
            "profit_risk": profit_risk,
            "inventory_risk": inventory_risk,
            "cash_flow_risk": cash_flow_risk,
            "compliance_risk": compliance_risk,
            "weights": self.RISK_WEIGHTS,
            "total_score": total_score,
            "risk_level": risk_level,
            "risk_level_label": level_label,
            "formula": (
                f"{profit_risk}*0.40 + {inventory_risk}*0.25 + "
                f"{cash_flow_risk}*0.20 + {compliance_risk}*0.15 = {total_score:.1f}"
            )
        }
        
        return risk_level, total_score, risk_breakdown, risk_details

    def _assess_profit_risk(self, current_margin: float, min_margin: float) -> float:
        """评估利润风险（0-100 分）"""
        if current_margin < min_margin * 0.5:
            return 100  # 利润严重不足
        elif current_margin < min_margin:
            return 70  # 利润不足
        elif current_margin < min_margin * 1.5:
            return 40  # 利润一般
        else:
            return 10  # 利润充足

    def _assess_inventory_risk(self, stock: int, stock_age_days: Optional[int]) -> float:
        """评估库存风险（0-100 分）"""
        if stock == 0:
            return 0  # 无库存风险
        
        if stock_age_days is None or stock_age_days == 0:
            return 20  # 默认低风险
        
        if stock_age_days > 180:
            return 100  # 严重积压
        elif stock_age_days > 120:
            return 70
        elif stock_age_days > 90:
            return 50
        elif stock_age_days > 60:
            return 30
        else:
            return 10

    def _assess_cash_flow_risk(self, cash_conversion_cycle: Optional[int]) -> float:
        """评估现金流风险（0-100 分）"""
        if cash_conversion_cycle is None:
            return 20  # 默认低风险
        
        if cash_conversion_cycle > 90:
            return 80  # 现金流紧张
        elif cash_conversion_cycle > 60:
            return 50
        elif cash_conversion_cycle > 30:
            return 30
        else:
            return 10

    def _assess_compliance_risk(self, refund_rate: float, complaint_rate: float) -> float:
        """评估合规风险（0-100 分）"""
        risk = 0
        
        # 退款率风险
        if refund_rate > 0.20:
            risk += 50
        elif refund_rate > 0.10:
            risk += 30
        elif refund_rate > 0.05:
            risk += 10
        
        # 投诉率风险
        if complaint_rate > 0.05:
            risk += 50
        elif complaint_rate > 0.02:
            risk += 30
        elif complaint_rate > 0.01:
            risk += 10
        
        return min(100, risk)

    def _check_promotion_feasibility_comprehensive(
        self,
        risk_level: str,
        current_price_compliant: bool,
        break_even_price: float,
        required_min_price: float,
        absolute_floor: Optional[float],
        current_price: float
    ) -> Tuple[bool, Optional[str], List[str]]:
        """
        综合判断是否允许促销（行使一票否决权）
        
        :return: (是否允许，否决理由，附加条件)
        """
        conditions = []
        
        # 一票否决条件 1：风险等级过高
        if risk_level == "high":
            return False, "综合风险等级为高，禁止促销以防止风险扩大", []

        # 一票否决条件 2：当前价格已不满足硬约束
        if not current_price_compliant:
            return False, f"当前价格 {current_price:.2f} 已低于约束要求的最低可执行价格 {required_min_price:.2f}", []
        
        # 一票否决条件 3：价格低于盈亏平衡点
        max_discount = break_even_price / current_price if current_price > 0 else 1.0
        if max_discount < 0.95:  # 接近盈亏平衡点
            conditions.append("警告：折扣已接近盈亏平衡点，建议谨慎决策")
        
        # 一票否决条件 4：低于品牌方限价
        if absolute_floor and (current_price * 0.9 < absolute_floor):
            return False, f"折扣后价格可能低于品牌方限价 ({absolute_floor})，禁止促销", []
        
        # 通过检查
        return True, None, conditions

    def _generate_risk_warnings(
        self,
        risk_level: str,
        current_margin: float,
        risk_data: RiskData,
        product: ProductBase,
        current_price_compliant: bool,
        required_min_price: float,
    ) -> List[str]:
        """生成风险预警列表"""
        warnings = []
        
        if current_margin < 0.15:
            warnings.append(f"当前毛利率较低 ({current_margin:.1%})，降价空间有限")
        
        if risk_data.refund_rate > 0.10:
            warnings.append(f"退款率偏高 ({risk_data.refund_rate:.1%})，需关注质量问题")
        
        if risk_data.complaint_rate > 0.02:
            warnings.append(f"投诉率偏高 ({risk_data.complaint_rate:.1%})，需改善服务")
        
        if product.stock_age_days and product.stock_age_days > 90:
            warnings.append(f"库龄较长 ({product.stock_age_days}天)，存在贬值风险")
        
        if risk_data.cash_conversion_cycle and risk_data.cash_conversion_cycle > 60:
            warnings.append(f"现金周转周期长 ({risk_data.cash_conversion_cycle}天)，注意现金流压力")
        
        if risk_data.is_brand_controlled and not risk_data.price_floor:
            warnings.append("品牌控价商品但未设置限价，请人工确认")

        if not current_price_compliant:
            warnings.append(f"当前售价已低于约束底线，至少应调整到 {required_min_price:.2f} 元")

        warnings.extend(risk_data.constraint_summary[:3])

        return self._dedupe_messages(warnings)

    def _generate_recommendation(
        self,
        allow_promotion: bool,
        risk_level: str,
        current_margin: float,
        min_margin: float,
        current_price_compliant: bool,
        required_min_price: float,
        current_price: float,
    ) -> Tuple[str, List[str]]:
        """生成建议"""
        reasons = []
        
        if not current_price_compliant:
            recommendation = "increase"
            reasons.append(f"当前售价 {current_price:.2f} 低于约束要求，建议至少调整到 {required_min_price:.2f}")
        elif not allow_promotion:
            recommendation = "maintain"
            reasons.append("综合风险评估未通过，建议维持原价")
        elif risk_level == "high":
            recommendation = "maintain"
            reasons.append("风险等级过高，不建议促销")
        elif current_margin < min_margin * 1.2:
            recommendation = "maintain"
            reasons.append("利润空间有限，建议维持原价")
        elif risk_level == "low" and current_margin > min_margin * 1.5:
            recommendation = "discount"
            reasons.append("风险较低且利润空间充足，可适度促销")
        else:
            recommendation = "maintain"
            reasons.append("风险与利润平衡，建议维持当前策略")
        
        return recommendation, self._dedupe_messages(reasons)

    def _dedupe_messages(self, values: List[str]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            deduped.append(cleaned)
        return deduped

    def _check_compliance(
        self,
        current_price: float,
        original_price: Optional[float],
        max_discount: float
    ) -> Tuple[bool, List[str]]:
        """
        合规性检查
        
        :return: (是否合规，问题列表)
        """
        issues = []
        
        # 检查 1：价格欺诈（先提价再打折）
        if original_price and original_price > current_price * 1.2:
            # 原价高于现价 20% 以上，疑似先提价再打折
            issues.append("警告：原价与现价差异过大，可能存在价格欺诈风险")
        
        # 检查 2：折扣幅度是否合理
        if max_discount < 0.5:
            issues.append("警告：折扣低于 5 折，可能违反平台规则")
        
        compliance_check = len(issues) == 0
        return compliance_check, issues

    def _get_fallback_result(self, request: AnalysisRequest) -> RiskControlResult:
        """返回降级结果（当分析失败时）"""
        product = request.product
        risk_data = request.risk_data
        
        # 保守估算
        current_margin = (product.current_price - product.cost) / product.current_price if product.current_price > 0 else 0
        min_safe_price = product.cost / (1 - risk_data.min_profit_margin) if risk_data.min_profit_margin < 1 else product.cost
        max_discount = min_safe_price / product.current_price if product.current_price > 0 else 1.0
        
        return RiskControlResult(
            current_profit_margin=current_margin,
            profit_margin_after_discount=current_margin,
            break_even_price=product.cost,
            min_safe_price=min_safe_price,
            required_min_price=max(min_safe_price, risk_data.price_floor or 0.0),
            absolute_price_floor=risk_data.price_floor,
            current_price_compliant=product.current_price >= max(min_safe_price, risk_data.price_floor or 0.0),
            risk_level="medium",
            risk_score=50.0,
            risk_breakdown={"profit_risk": 50, "inventory_risk": 20, "cash_flow_risk": 20, "compliance_risk": 10},
            allow_promotion=current_margin > risk_data.min_profit_margin,
            max_safe_discount=max(0.5, min(1.0, max_discount)),
            discount_conditions=["分析过程发生错误，使用保守估算"],
            warnings=["风控分析失败，建议人工介入"],
            recommendation="maintain",
            recommendation_reasons=["风控分析失败，建议维持原价"],
            constraint_summary=risk_data.constraint_summary,
            calculation_details={"error": "分析过程中发生错误"},
            compliance_check=True,
            veto_reason=None
        )
