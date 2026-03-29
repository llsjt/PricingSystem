from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.crew.crew_factory import build_crew_bundle
from app.crew.protocols import CrewRunPayload
from app.schemas.result import TaskFinalResult
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool
from app.utils.math_utils import money


class OrchestrationService:
    """4 Agent MVP 编排服务：顺序执行并写入完整卡片。"""

    def __init__(self, db: Session):
        self.db = db
        self.bundle = build_crew_bundle()
        self.log_tool = LogWriterTool(db)
        self.result_tool = ResultWriterTool(db)

    @staticmethod
    def _price_range(min_price: Decimal, max_price: Decimal) -> dict[str, float]:
        return {
            "min": float(money(min_price)),
            "max": float(money(max_price)),
        }

    @staticmethod
    def _to_float(value: Decimal | int | float) -> float:
        if isinstance(value, Decimal):
            return float(money(value))
        return float(value)

    def _build_data_card(
        self,
        payload: CrewRunPayload,
        data_result: Any,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        # 仅输出可公开摘要，不暴露原始 chain-of-thought。
        thinking = "基于内部经营数据评估价格弹性与利润-销量关系，给出稳态建议区间。"
        evidence = [
            {
                "label": "策略目标",
                "value": payload.strategy_goal,
            },
            {
                "label": "基线销量(月)",
                "value": int(payload.baseline_sales),
            },
            {
                "label": "基线利润(月)",
                "value": self._to_float(payload.baseline_profit),
            },
            {
                "label": "当前售价",
                "value": self._to_float(payload.product.current_price),
            },
            {
                "label": "成本价",
                "value": self._to_float(payload.product.cost_price),
            },
        ]
        suggestion = {
            "priceRange": self._price_range(data_result.suggested_min_price, data_result.suggested_max_price),
            "recommendedPrice": self._to_float(data_result.suggested_price),
            "expectedSales": int(data_result.expected_sales),
            "expectedProfit": self._to_float(data_result.expected_profit),
            "expectedProfitRate": round(
                self._to_float(data_result.expected_profit)
                / max(self._to_float(data_result.suggested_price) * max(int(data_result.expected_sales), 1), 0.01),
                4,
            ),
            "summary": data_result.summary,
        }
        return thinking, evidence, suggestion

    def _build_market_card(
        self,
        competitors: list[dict[str, Any]],
        market_result: Any,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        thinking = "基于模拟竞品快照识别价格带、促销强度与平台分布，输出市场可接受建议价。"

        price_values = [float(item.get("price", 0) or 0) for item in competitors if item.get("price") is not None]
        if price_values:
            spread = max(price_values) - min(price_values)
            market_score = max(40.0, min(95.0, 88.0 - spread / max(sum(price_values) / len(price_values), 1) * 25.0))
        else:
            market_score = 55.0

        evidence = [
            {
                "label": "竞品样本数",
                "value": len(competitors),
            },
            {
                "label": "竞品摘要",
                "value": [
                    {
                        "competitorName": item.get("competitorName"),
                        "price": item.get("price"),
                        "originalPrice": item.get("originalPrice"),
                        "salesVolumeHint": item.get("salesVolumeHint"),
                        "promotionTag": item.get("promotionTag"),
                        "shopType": item.get("shopType"),
                        "sourcePlatform": item.get("sourcePlatform"),
                    }
                    for item in competitors[:6]
                ],
            },
        ]
        suggestion = {
            "priceRange": self._price_range(market_result.market_floor, market_result.market_ceiling),
            "recommendedPrice": self._to_float(market_result.suggested_price),
            "marketScore": round(market_score, 2),
            "summary": market_result.summary,
        }
        return thinking, evidence, suggestion

    def _build_risk_card(
        self,
        payload: CrewRunPayload,
        candidate_price: Decimal,
        risk_result: Any,
        data_result: Any,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        expected_sales = int(data_result.expected_sales)
        expected_profit = money((money(risk_result.suggested_price) - money(payload.product.cost_price)) * expected_sales)

        no_negative_profit = money(risk_result.suggested_price) >= money(payload.product.cost_price)
        better_than_baseline = expected_profit > money(payload.baseline_profit)
        hard_pass = bool(risk_result.is_pass) and no_negative_profit and better_than_baseline

        if hard_pass:
            action = "AUTO_EXECUTE"
            summary = "满足硬约束，建议自动执行。"
        else:
            action = "MANUAL_REVIEW"
            summary = "触发硬约束，需人工复核。"

        thinking = "执行成本底线与利润提升双硬约束校验，判断是否允许自动执行。"
        evidence = [
            {
                "label": "候选价格",
                "value": self._to_float(candidate_price),
            },
            {
                "label": "风控建议价",
                "value": self._to_float(risk_result.suggested_price),
            },
            {
                "label": "安全底价",
                "value": self._to_float(risk_result.safe_floor_price),
            },
            {
                "label": "基线利润(月)",
                "value": self._to_float(payload.baseline_profit),
            },
            {
                "label": "按风控价估算利润(月)",
                "value": self._to_float(expected_profit),
            },
            {
                "label": "硬约束-不亏损",
                "value": no_negative_profit,
            },
            {
                "label": "硬约束-利润高于基线",
                "value": better_than_baseline,
            },
        ]
        suggestion = {
            "recommendedPrice": self._to_float(risk_result.suggested_price),
            "pass": hard_pass,
            "riskLevel": risk_result.risk_level,
            "action": action,
            "summary": summary,
        }
        return thinking, evidence, suggestion

    def _build_manager_reason(
        self,
        data_price: Decimal,
        market_price: Decimal,
        final_price: Decimal,
        risk_auto_pass: bool,
        strategy: str,
    ) -> str:
        return (
            f"未直接采用数据分析Agent价格 {money(data_price)}，因为该价格侧重内部经营信号，"
            "对竞品促销强度的吸收不足；"
            f"未直接采用市场情报Agent价格 {money(market_price)}，因为其更强调市场接受度，"
            "但未完全覆盖利润底线约束。"
            f"风险控制Agent对自动执行的判断为 {'可接受' if risk_auto_pass else '不接受'}，"
            "核心依据是成本底线与利润提升硬约束。"
            f"最终选择 {money(final_price)} 作为折中建议，执行策略为“{strategy}”，"
            "兼顾盈利、成交与风控可执行性。"
        )

    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        """顺序执行 4 个 Agent，并在每一步落库完整卡片。"""
        data_result = self.bundle.data_agent.run(
            product=payload.product,
            metrics=payload.metrics,
            traffic=payload.traffic,
            strategy_goal=payload.strategy_goal,
        )
        data_thinking, data_evidence, data_suggestion = self._build_data_card(payload, data_result)
        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=self.bundle.data_agent.name,
            display_order=1,
            thinking_summary=data_thinking,
            evidence=data_evidence,
            suggestion=data_suggestion,
        )

        competitors = self.bundle.market_agent.competitor_service.get_competitors(
            product_id=payload.product.product_id,
            product_title=payload.product.product_name,
            category_name=payload.product.category_name,
            current_price=payload.product.current_price,
        )
        market_result = self.bundle.market_agent.run(product=payload.product, strategy_goal=payload.strategy_goal)
        market_thinking, market_evidence, market_suggestion = self._build_market_card(competitors, market_result)
        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=self.bundle.market_agent.name,
            display_order=2,
            thinking_summary=market_thinking,
            evidence=market_evidence,
            suggestion=market_suggestion,
        )

        candidate_price = money((data_result.suggested_price + market_result.suggested_price) / Decimal("2"))
        risk_result = self.bundle.risk_agent.run(
            current_price=payload.product.current_price,
            cost_price=payload.product.cost_price,
            candidate_price=candidate_price,
            constraints=payload.constraints,
        )
        risk_thinking, risk_evidence, risk_suggestion = self._build_risk_card(payload, candidate_price, risk_result, data_result)
        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=self.bundle.risk_agent.name,
            display_order=3,
            thinking_summary=risk_thinking,
            evidence=risk_evidence,
            suggestion=risk_suggestion,
        )

        manager_result = self.bundle.manager_agent.run(
            strategy_goal=payload.strategy_goal,
            current_price=payload.product.current_price,
            cost_price=payload.product.cost_price,
            baseline_profit=payload.baseline_profit,
            baseline_sales=payload.baseline_sales,
            data_result=data_result,
            market_result=market_result,
            risk_result=risk_result,
            crewai_hint=None,
        )

        # 严格执行硬约束：不亏损 + 利润高于基线。
        hard_pass = (
            money(manager_result.final_price) >= money(payload.product.cost_price)
            and money(manager_result.expected_profit) > money(payload.baseline_profit)
        )
        if not hard_pass:
            manager_result.is_pass = False
            manager_result.execute_strategy = "人工审核"

        manager_reason = self._build_manager_reason(
            data_price=data_result.suggested_price,
            market_price=market_result.suggested_price,
            final_price=manager_result.final_price,
            risk_auto_pass=bool(risk_suggestion.get("pass")),
            strategy=manager_result.execute_strategy,
        )

        manager_thinking = "综合前三个Agent的依据与建议，输出可执行的最终价格与策略。"
        manager_evidence = [
            {
                "label": "数据分析建议价",
                "value": self._to_float(data_result.suggested_price),
            },
            {
                "label": "市场情报建议价",
                "value": self._to_float(market_result.suggested_price),
            },
            {
                "label": "风险控制建议价",
                "value": self._to_float(risk_result.suggested_price),
            },
            {
                "label": "风控自动通过",
                "value": bool(risk_suggestion.get("pass")),
            },
        ]
        manager_suggestion = {
            "finalPrice": self._to_float(manager_result.final_price),
            "expectedSales": int(manager_result.expected_sales),
            "expectedProfit": self._to_float(manager_result.expected_profit),
            "strategy": manager_result.execute_strategy,
            "summary": manager_result.result_summary,
        }
        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=self.bundle.manager_agent.name,
            display_order=4,
            thinking_summary=manager_thinking,
            evidence=manager_evidence,
            suggestion=manager_suggestion,
            reason_why=manager_reason,
        )

        final_payload = TaskFinalResult(
            taskId=payload.task_id,
            finalPrice=manager_result.final_price,
            expectedSales=manager_result.expected_sales,
            expectedProfit=manager_result.expected_profit,
            profitGrowth=manager_result.profit_growth,
            isPass=bool(manager_result.is_pass),
            executeStrategy=manager_result.execute_strategy,
            resultSummary=manager_result.result_summary,
            suggestedMinPrice=manager_result.suggested_min_price,
            suggestedMaxPrice=manager_result.suggested_max_price,
        )
        self.result_tool.write_final_result(final_payload)
        return final_payload
