import logging
from typing import Any, Dict, List, Tuple

from app.schemas.decision import (
    AgentSummary,
    AnalysisRequest,
    ConflictResolution,
    DataAnalysisResult,
    ExecutionPlan,
    ExpectedOutcomes,
    FinalDecision,
    MarketIntelResult,
    RiskControlResult,
)

logger = logging.getLogger(__name__)


class ManagerCoordinatorAgent:
    DATA_AGENT = "数据分析"
    MARKET_AGENT = "市场情报"
    RISK_AGENT = "风险控制"

    STRATEGY_LABELS = {
        "MAX_PROFIT": "利润优先",
        "CLEARANCE": "清仓优先",
        "MARKET_SHARE": "市场份额优先",
        "BRAND_BUILDING": "品牌建设优先",
    }

    def coordinate(
        self,
        request: AnalysisRequest,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> FinalDecision:
        try:
            conflicts, conflict_summary = self._detect_conflicts(data_result, market_result, risk_result)
            decision, discount_rate, core_reason_items, key_factors = self._make_final_decision(
                request,
                data_result,
                market_result,
                risk_result,
                conflict_summary,
            )

            confidence = self._calculate_confidence(data_result, market_result, risk_result, conflicts)
            if decision == "increase":
                suggested_price = round(max(risk_result.required_min_price, request.product.current_price * discount_rate), 2)
                discount_rate = round(suggested_price / max(request.product.current_price, 0.01), 4)
            else:
                suggested_price = round(request.product.current_price * discount_rate, 2)
            warnings = self._build_warnings(risk_result, conflicts, decision)
            risk_warning = self._merge_statements(warnings) if warnings else "当前方案未发现需要立即阻断的风险。"
            expected_outcomes = self._estimate_outcomes(
                decision,
                discount_rate,
                data_result,
                market_result,
                risk_result,
            )
            execution_plan = self._build_execution_plan(decision, suggested_price)
            agent_summaries = self._build_agent_summaries(data_result, market_result, risk_result)
            structured_summaries = self._build_structured_summaries(data_result, market_result, risk_result)

            strategy_label = self.STRATEGY_LABELS.get(request.strategy_goal, "平衡目标")
            thinking_process = self._build_thinking_process(
                request,
                strategy_label,
                data_result,
                market_result,
                risk_result,
                conflict_summary,
            )
            reasoning = self._build_reasoning(strategy_label, decision, discount_rate, risk_result)
            core_reasons = self._merge_statements(core_reason_items)
            report_text = self._build_report(
                request,
                decision,
                discount_rate,
                suggested_price,
                thinking_process,
                reasoning,
                core_reasons,
                conflict_summary,
            )

            return FinalDecision(
                decision=decision,
                discount_rate=discount_rate,
                suggested_price=suggested_price,
                confidence=confidence,
                expected_outcomes=expected_outcomes,
                core_reasons=core_reasons,
                key_factors=key_factors,
                conflicts_detected=conflicts,
                risk_warning=risk_warning,
                contingency_plan=self._build_contingency_plan(decision),
                execution_plan=execution_plan,
                report_text=report_text,
                agent_summaries=agent_summaries,
                decision_framework=self._build_decision_framework(strategy_label, conflicts, decision, discount_rate),
                alternative_options=self._build_alternatives(discount_rate, risk_result),
                thinking_process=thinking_process,
                reasoning=reasoning,
                conflict_summary=conflict_summary,
                warnings=warnings,
                agent_summaries_structured=structured_summaries,
            )
        except Exception:
            logger.exception("ManagerCoordinatorAgent failed for product %s", request.product.product_id)
            return self._fallback_decision(request)

    def _detect_conflicts(
        self,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> Tuple[List[ConflictResolution], str]:
        conflicts: List[ConflictResolution] = []

        data_supports_promotion = data_result.recommended_action in {"discount", "clearance"}
        market_supports_promotion = market_result.market_suggestion in {"price_war", "penetrate", "discount"}
        data_min_rate = data_result.recommended_discount_range[0]
        risk_min_rate = risk_result.max_safe_discount

        if data_supports_promotion and data_min_rate < risk_min_rate:
            conflicts.append(
                ConflictResolution(
                    agent1=self.DATA_AGENT,
                    agent2=self.RISK_AGENT,
                    conflict=(
                        f"数据分析建议的最低价格系数为 {data_min_rate:.2f}，"
                        f"低于风险控制允许的最低安全系数 {risk_min_rate:.2f}。"
                    ),
                    resolution=(
                        f"最终采用风险控制底线 {risk_min_rate:.2f} 作为促销下限，"
                        "避免折扣穿透利润安全线。"
                    ),
                    priority="risk_control",
                )
            )

        if market_supports_promotion and not risk_result.allow_promotion:
            conflicts.append(
                ConflictResolution(
                    agent1=self.MARKET_AGENT,
                    agent2=self.RISK_AGENT,
                    conflict="市场情报建议跟进促销，但风险控制未通过促销审批。",
                    resolution="风险控制否决促销，本轮维持现价。",
                    priority="risk_control_veto",
                )
            )

        if market_supports_promotion and not data_supports_promotion:
            conflicts.append(
                ConflictResolution(
                    agent1=self.MARKET_AGENT,
                    agent2=self.DATA_AGENT,
                    conflict="市场情报支持促销，但内部经营数据没有给出强促销信号。",
                    resolution="由经理结合目标方向和风险边界，决定是否执行小幅促销。",
                    priority="manager_alignment",
                )
            )

        if not conflicts:
            return [], ""

        return conflicts, self._merge_statements([conflict.resolution for conflict in conflicts])

    def _make_final_decision(
        self,
        request: AnalysisRequest,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
        conflict_summary: str,
    ) -> Tuple[str, float, List[str], List[str]]:
        core_reasons: List[str] = []
        key_factors: List[str] = []

        data_supports_promotion = data_result.recommended_action in {"discount", "clearance"}
        market_supports_promotion = market_result.market_suggestion in {"price_war", "penetrate", "discount"}
        current_price = max(request.product.current_price, 0.01)

        if not risk_result.current_price_compliant:
            required_rate = risk_result.required_min_price / current_price
            core_reasons.append(
                f"当前价格 {request.product.current_price:.2f} 低于约束要求的最低可执行价格 {risk_result.required_min_price:.2f}"
            )
            core_reasons.extend(risk_result.constraint_summary[:2])
            if conflict_summary:
                core_reasons.append(conflict_summary)
            return "increase", required_rate, core_reasons, ["硬约束优先", "价格底线"]

        if not risk_result.allow_promotion:
            core_reasons.append(risk_result.veto_reason or "风险控制未通过促销审批")
            core_reasons.append("当前利润空间或风险条件不足以支持折扣")
            if conflict_summary:
                core_reasons.append(conflict_summary)
            return "maintain", 1.0, core_reasons, ["风险控制否决", "利润安全线"]

        if request.strategy_goal == "CLEARANCE":
            should_promote = data_supports_promotion or risk_result.allow_promotion
            key_factors.append("清仓优先")
        elif request.strategy_goal == "MARKET_SHARE":
            should_promote = market_supports_promotion or data_supports_promotion
            key_factors.append("市场份额优先")
        else:
            should_promote = data_supports_promotion or (
                market_supports_promotion and market_result.competition_level == "fierce"
            )
            key_factors.append("利润与销量平衡")

        if not should_promote:
            core_reasons.append("内部经营数据和市场信号都不足以支持立即促销")
            core_reasons.append("在可促销前提下，维持现价更符合当前业务目标")
            return "maintain", 1.0, core_reasons, key_factors

        if data_supports_promotion:
            lower_rate = max(data_result.recommended_discount_range[0], risk_result.max_safe_discount)
            upper_rate = max(lower_rate, data_result.recommended_discount_range[1])
        else:
            lower_rate = risk_result.max_safe_discount
            upper_rate = 1.0

        if request.strategy_goal in {"CLEARANCE", "MARKET_SHARE"}:
            discount_rate = lower_rate
        else:
            discount_rate = round((lower_rate + upper_rate) / 2, 2)

        if market_result.market_suggestion in {"price_war", "penetrate"} and market_result.competition_level == "fierce":
            discount_rate = lower_rate
            key_factors.append("竞争压力")

        if data_result.inventory_status in {"severe_overstock", "overstock"}:
            discount_rate = min(discount_rate, round(lower_rate, 2))
            key_factors.append("库存压力")

        discount_rate = round(max(risk_result.max_safe_discount, min(discount_rate, 1.0)), 2)

        if discount_rate >= 0.99:
            core_reasons.append("综合判断后，更适合维持现价")
            if conflict_summary:
                core_reasons.append(conflict_summary)
            return "maintain", 1.0, core_reasons, key_factors

        core_reasons.append(
            f"销量趋势为{self._translate_sales_trend(data_result.sales_trend)}，库存状态为{self._translate_inventory_status(data_result.inventory_status)}"
        )
        core_reasons.append(
            f"市场竞争强度为{self._translate_competition_level(market_result.competition_level)}，当前价格定位为{self._translate_price_position(market_result.price_position)}"
        )
        core_reasons.append(
            f"风险控制允许的最低安全价格系数为 {risk_result.max_safe_discount:.2f}，最终建议系数为 {discount_rate:.2f}"
        )
        if conflict_summary:
            core_reasons.append(conflict_summary)

        return "discount", discount_rate, core_reasons, key_factors

    def _calculate_confidence(
        self,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
        conflicts: List[ConflictResolution],
    ) -> float:
        confidence = (
            data_result.recommendation_confidence * 0.35
            + market_result.suggestion_confidence * 0.25
            + max(0.0, 1 - risk_result.risk_score / 100.0) * 0.30
            + (0.10 if not conflicts else 0.05)
        )
        return round(max(0.3, min(0.95, confidence)), 2)

    def _estimate_outcomes(
        self,
        decision: str,
        discount_rate: float,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> ExpectedOutcomes:
        if decision == "increase":
            price_lift = max(0.0, discount_rate - 1.0)
            sales_lift = round(max(0.85, 1 - price_lift * 0.4), 2)
            profit_change = round(max(0.0, price_lift * 0.8), 3)
            return ExpectedOutcomes(sales_lift=sales_lift, profit_change=profit_change, market_share_change=-0.01)

        if decision != "discount":
            return ExpectedOutcomes(sales_lift=1.0, profit_change=0.0, market_share_change=0.0)

        price_cut = max(0.0, 1 - discount_rate)
        elasticity = abs(data_result.demand_elasticity or -1.2)
        competition_bonus = 0.05 if market_result.competition_level == "fierce" else 0.0
        sales_lift = round(max(1.0, 1 + price_cut * elasticity * 1.2 + competition_bonus), 2)

        current_margin = max(0.0, risk_result.current_profit_margin)
        next_margin = max(0.0, risk_result.profit_margin_after_discount or current_margin)
        profit_change = round((sales_lift * next_margin - current_margin) / max(current_margin, 0.01), 3)
        market_share_change = round(min(0.08, price_cut * 0.50 + competition_bonus), 3)

        return ExpectedOutcomes(
            sales_lift=sales_lift,
            profit_change=profit_change,
            market_share_change=market_share_change,
        )

    def _build_warnings(
        self,
        risk_result: RiskControlResult,
        conflicts: List[ConflictResolution],
        decision: str,
    ) -> List[str]:
        warnings = [self._strip_trailing_punctuation(item) for item in risk_result.warnings[:3] if item]
        if not risk_result.current_price_compliant:
            warnings.append(f"当前价格未满足硬约束，需先修正到 {risk_result.required_min_price:.2f} 元")
        if conflicts:
            warnings.append("存在分析分歧，最终方案已按经理协调和风险边界收敛")
        if decision == "discount" and risk_result.risk_level == "medium":
            warnings.append("执行促销后需要跟踪利润率和退款率，必要时及时回调价格")
        return warnings

    def _build_execution_plan(self, decision: str, suggested_price: float) -> List[ExecutionPlan]:
        if decision == "increase":
            return [
                ExecutionPlan(step=1, action=f"将商品价格上调至 {suggested_price:.2f}", timing="立即执行", responsible="运营"),
                ExecutionPlan(step=2, action="同步检查详情页、活动页和渠道报价，确保全链路满足约束", timing="2小时内", responsible="运营"),
                ExecutionPlan(step=3, action="重点监控转化率、销量波动和用户反馈", timing="提价后24小时内", responsible="数据分析"),
            ]

        if decision == "discount":
            return [
                ExecutionPlan(step=1, action=f"将商品价格调整为 {suggested_price:.2f}", timing="立即执行", responsible="运营"),
                ExecutionPlan(step=2, action="同步更新详情页和活动页", timing="2小时内", responsible="运营"),
                ExecutionPlan(step=3, action="监控销量利润和退款率变化", timing="促销开始后", responsible="数据分析"),
            ]

        return [
            ExecutionPlan(step=1, action="维持当前价格不变", timing="立即执行", responsible="运营"),
            ExecutionPlan(step=2, action="持续监控市场价格和库存变化", timing="每日监控", responsible="市场"),
        ]

    def _build_agent_summaries(
        self,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> List[AgentSummary]:
        return [
            AgentSummary(
                agent_name=self.DATA_AGENT,
                summary=(
                    f"销量趋势{self._translate_sales_trend(data_result.sales_trend)}，"
                    f"库存状态{self._translate_inventory_status(data_result.inventory_status)}。"
                ),
                key_points=data_result.recommendation_reasons[:3],
            ),
            AgentSummary(
                agent_name=self.MARKET_AGENT,
                summary=(
                    f"竞争强度{self._translate_competition_level(market_result.competition_level)}，"
                    f"价格定位{self._translate_price_position(market_result.price_position)}。"
                ),
                key_points=market_result.suggestion_reasons[:3],
            ),
            AgentSummary(
                agent_name=self.RISK_AGENT,
                summary=(
                    f"风险等级{self._translate_risk_level(risk_result.risk_level)}，"
                    f"促销审批{'通过' if risk_result.allow_promotion else '未通过'}。"
                ),
                key_points=risk_result.recommendation_reasons[:3],
            ),
        ]

    def _build_structured_summaries(
        self,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
    ) -> Dict[str, Any]:
        return {
            "dataAnalysis": {
                "salesTrend": self._translate_sales_trend(data_result.sales_trend),
                "inventoryStatus": self._translate_inventory_status(data_result.inventory_status),
                "suggestedDiscountRange": self._format_discount_range(data_result.recommended_discount_range),
            },
            "marketIntel": {
                "competitionLevel": self._translate_competition_level(market_result.competition_level),
                "pricePosition": self._translate_price_position(market_result.price_position),
                "marketSuggestion": self._translate_market_suggestion(market_result.market_suggestion),
            },
            "riskControl": {
                "riskLevel": self._translate_risk_level(risk_result.risk_level),
                "currentPriceCompliant": "是" if risk_result.current_price_compliant else "否",
                "requiredMinPrice": round(risk_result.required_min_price, 2),
                "profitMarginAfterDiscount": {
                    self._format_single_discount(risk_result.max_safe_discount): round(
                        risk_result.profit_margin_after_discount or risk_result.current_profit_margin,
                        3,
                    )
                },
                "safeDiscountRange": self._format_safe_discount_range(risk_result.max_safe_discount),
            },
        }

    def _build_thinking_process(
        self,
        request: AnalysisRequest,
        strategy_label: str,
        data_result: DataAnalysisResult,
        market_result: MarketIntelResult,
        risk_result: RiskControlResult,
        conflict_summary: str,
    ) -> str:
        parts = [
            (
                "我先汇总了数据分析、市场情报和风险控制的输出，"
                f"确认销量趋势为{self._translate_sales_trend(data_result.sales_trend)}，"
                f"库存状态为{self._translate_inventory_status(data_result.inventory_status)}。"
            ),
            (
                f"随后结合市场竞争强度{self._translate_competition_level(market_result.competition_level)}和"
                f"价格定位{self._translate_price_position(market_result.price_position)}，"
                "判断是否需要跟进促销。"
            ),
            (
                f"最后校验风险边界，当前促销审批结果为"
                f"{'通过' if risk_result.allow_promotion else '未通过'}，"
                f"最低安全价格系数为 {risk_result.max_safe_discount:.2f}。"
            ),
            f"本轮业务目标为{strategy_label}。"
        ]
        if not risk_result.current_price_compliant:
            parts.append(f"校验发现当前价格未满足硬约束，最低可执行价格应为 {risk_result.required_min_price:.2f} 元。")
        if request.strategy_constraints:
            parts.append(
                f"本轮还考虑了约束条件 {self._strip_trailing_punctuation(request.strategy_constraints)}。"
            )
        if conflict_summary:
            parts.append(
                f"在协调阶段处理了以下分歧 {self._strip_trailing_punctuation(conflict_summary)}。"
            )
        return "".join(parts)

    def _build_reasoning(
        self,
        strategy_label: str,
        decision: str,
        discount_rate: float,
        risk_result: RiskControlResult,
    ) -> str:
        if decision == "increase":
            return (
                "综合经营数据、市场竞争和风险边界后，当前价格首先需要满足硬约束。"
                f"结合{strategy_label}的要求，现价低于最低可执行价格 {risk_result.required_min_price:.2f} 元，"
                "因此本轮优先修正价格底线，而不是继续维持现价或促销。"
            )

        if decision == "discount":
            return (
                "综合经营数据、市场竞争和风险边界后，促销方向成立。"
                f"结合{strategy_label}的要求，最终将折扣控制在风险控制允许的范围内，"
                f"建议执行 {self._format_single_discount(discount_rate)}。"
            )

        veto_text = self._strip_trailing_punctuation(risk_result.veto_reason or "当前条件不适合执行促销")
        return f"虽然部分信号支持促销，但综合判断后认为 {veto_text}，因此本轮维持现价。"

    def _build_decision_framework(
        self,
        strategy_label: str,
        conflicts: List[ConflictResolution],
        decision: str,
        discount_rate: float,
    ) -> str:
        if decision == "maintain":
            decision_text = "维持现价"
        elif decision == "increase":
            decision_text = "执行提价"
        else:
            decision_text = f"执行 {self._format_single_discount(discount_rate)}"
        return (
            "先看内部经营数据，再看外部竞争压力，最后由风险控制确定安全边界。"
            f"本轮目标为{strategy_label}，识别到 {len(conflicts)} 个分歧点，"
            f"最终输出为 {decision_text}。"
        )

    def _build_alternatives(self, discount_rate: float, risk_result: RiskControlResult) -> List[Dict[str, Any]]:
        options: List[Dict[str, Any]] = [
            {
                "option": "维持现价",
                "pros": ["利润最稳定", "执行成本最低"],
                "cons": ["销量拉动有限", "竞争压力下可能偏保守"],
            }
        ]

        if not risk_result.current_price_compliant:
            options.insert(
                0,
                {
                    "option": f"提价至 {risk_result.required_min_price:.2f}",
                    "pros": ["立即满足硬约束", "避免继续执行不合规价格"],
                    "cons": ["短期内可能影响转化率"],
                },
            )

        safe_rate = round(max(risk_result.max_safe_discount, min(discount_rate, 1.0)), 2)
        if safe_rate < 1.0:
            options.append(
                {
                    "option": f"执行 {self._format_single_discount(safe_rate)}",
                    "pros": ["兼顾销量刺激和利润安全", "与风险边界一致"],
                    "cons": ["需要持续监控执行效果"],
                }
            )
        return options

    def _build_report(
        self,
        request: AnalysisRequest,
        decision: str,
        discount_rate: float,
        suggested_price: float,
        thinking_process: str,
        reasoning: str,
        core_reasons: str,
        conflict_summary: str,
    ) -> str:
        if decision == "maintain":
            decision_text = "维持现价"
        elif decision == "increase":
            decision_text = "提价"
        else:
            decision_text = f"执行 {self._format_single_discount(discount_rate)}"
        sections = [
            f"思考过程：{thinking_process}",
            f"分析理由：{reasoning}",
            f"核心依据：{core_reasons}",
        ]
        if conflict_summary:
            sections.append(f"冲突处理：{conflict_summary}")
        sections.append(
            f"最终决定：建议{decision_text}，建议价格为 {suggested_price:.2f}，商品为 {request.product.product_name}。"
        )
        return "\n".join(sections)

    def _build_contingency_plan(self, decision: str) -> str:
        if decision == "increase":
            return "如果提价后转化率明显下滑，需要重新复核约束条件与市场接受度，再决定是否进入人工审批。"
        if decision == "discount":
            return "如果利润率、退款率或竞品反应超出预期，立即回调价格并重新发起决策任务。"
        return "继续监控销量、库存和竞品价格，一旦出现明显变化则重新分析。"

    def _fallback_decision(self, request: AnalysisRequest) -> FinalDecision:
        return FinalDecision(
            decision="maintain",
            discount_rate=1.0,
            suggested_price=request.product.current_price,
            confidence=0.3,
            expected_outcomes=ExpectedOutcomes(sales_lift=1.0, profit_change=0.0, market_share_change=0.0),
            core_reasons="经理协调执行失败，已回退为保守决策。",
            key_factors=["系统降级"],
            conflicts_detected=[],
            risk_warning="自动回退为保守方案，请检查日志。",
            contingency_plan="人工复核后重新执行任务。",
            execution_plan=[ExecutionPlan(step=1, action="人工复核当前定价", timing="立即执行", responsible="运营")],
            report_text="思考过程：经理协调执行失败。\n分析理由：系统已回退到保守策略。\n核心依据：系统异常。\n最终决定：维持现价。",
            agent_summaries=[],
            decision_framework="降级模式",
            alternative_options=[],
            thinking_process="我在整合三个分析结果时发生异常，无法继续自动协调。",
            reasoning="为避免错误决策影响价格执行，系统回退为保守方案。",
            conflict_summary="",
            warnings=["经理协调执行失败"],
            agent_summaries_structured={},
        )

    def _merge_statements(self, items: List[str]) -> str:
        cleaned = [self._strip_trailing_punctuation(item) for item in items if item and item.strip()]
        if not cleaned:
            return ""
        return "；".join(cleaned) + "。"

    def _strip_trailing_punctuation(self, value: str) -> str:
        return value.strip().rstrip("。；;，,")

    def _translate_sales_trend(self, value: str) -> str:
        mapping = {
            "rapid_rising": "快速上升",
            "rising": "上升",
            "stable": "稳定",
            "declining": "下降",
            "rapid_declining": "快速下降",
        }
        return mapping.get(value, value)

    def _translate_inventory_status(self, value: str) -> str:
        mapping = {
            "severe_overstock": "严重积压",
            "overstock": "积压",
            "normal": "正常",
            "tight": "偏紧",
            "shortage": "短缺",
        }
        return mapping.get(value, value)

    def _translate_competition_level(self, value: str) -> str:
        mapping = {"fierce": "高", "moderate": "中", "low": "低"}
        return mapping.get(value, value)

    def _translate_price_position(self, value: str) -> str:
        mapping = {"premium": "偏高", "mid-range": "居中", "budget": "偏低"}
        return mapping.get(value, value)

    def _translate_market_suggestion(self, value: str) -> str:
        mapping = {
            "price_war": "建议跟进促销",
            "penetrate": "建议主动压价",
            "discount": "建议短期促销",
            "differentiate": "建议差异化竞争",
            "premium": "建议尝试提价",
            "maintain": "建议维持现价",
        }
        return mapping.get(value, value)

    def _translate_risk_level(self, value: str) -> str:
        mapping = {"high": "高", "medium": "中", "low": "低"}
        return mapping.get(value, value)

    def _format_discount_range(self, rate_range: Tuple[float, float]) -> str:
        low_off = round((1 - rate_range[1]) * 100)
        high_off = round((1 - rate_range[0]) * 100)
        if low_off == high_off:
            return f"{low_off}%"
        return f"{low_off}%-{high_off}%"

    def _format_safe_discount_range(self, min_rate: float) -> str:
        return f"0%-{round((1 - min_rate) * 100)}%"

    def _format_single_discount(self, rate: float) -> str:
        if rate >= 1.0:
            return "不打折"
        return f"{rate * 10:.1f} 折"
