import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, inspect
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.ws_manager import manager
from app.models.db_models import BizProduct, BizPromotionHistory, BizSalesDaily, DecAgentLog, DecResult, DecTask
from app.schemas.decision import AnalysisRequest, CompetitorData, ProductBase, RiskData, SalesData
from app.services.decision_service import decision_service

logger = logging.getLogger(__name__)


class WorkflowService:
    DATA_ROLE = "数据分析"
    MARKET_ROLE = "市场情报"
    RISK_ROLE = "风险控制"
    MANAGER_ROLE = "经理协调"

    def __init__(self):
        self._promotion_history_table_exists: Optional[bool] = None

    async def execute_task(self, task_id: int, product_ids: List[int], strategy_goal: str, constraints: str):
        logger.info("Starting workflow for task %s with products %s", task_id, product_ids)
        self.update_task_status(task_id, "RUNNING")

        for product_id in product_ids:
            try:
                await self.process_single_product(task_id, product_id, strategy_goal, constraints)
            except Exception as exc:
                logger.exception("Error processing product %s for task %s", product_id, task_id)
                await manager.broadcast(
                    json.dumps({"type": "error", "product_id": product_id, "message": str(exc)}),
                    str(task_id),
                )

        self.update_task_status(task_id, "COMPLETED")
        await manager.broadcast(json.dumps({"type": "complete", "task_id": task_id}), str(task_id))

    def update_task_status(self, task_id: int, status: str):
        db: Session = SessionLocal()
        try:
            task = db.query(DecTask).filter(DecTask.id == task_id).first()
            if task:
                task.status = status
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to update task %s status to %s", task_id, status)
        finally:
            db.close()

    async def process_single_product(self, task_id: int, product_id: int, strategy_goal: str, constraints: str):
        db: Session = SessionLocal()
        try:
            product = db.query(BizProduct).filter(BizProduct.id == product_id).first()
            if not product:
                raise ValueError(f"Product {product_id} not found")

            parsed_constraints = self.parse_constraint_bundle(constraints)

            request_data = AnalysisRequest(
                task_id=str(task_id),
                product=ProductBase(
                    product_id=str(product.id),
                    product_name=product.title,
                    category=product.category or "Unknown",
                    current_price=float(product.current_price),
                    cost=float(product.cost_price),
                    original_price=float(product.market_price) if product.market_price is not None else None,
                    stock=int(product.stock or 0),
                ),
                sales_data=await self.fetch_sales_data(db, product_id),
                competitor_data=await self.build_competitor_data(product),
                risk_data=await self.build_risk_data(parsed_constraints, product),
                customer_reviews=[],
                strategy_goal=strategy_goal,
                strategy_constraints=constraints,
                business_context={"parsed_constraints": parsed_constraints},
            )

            data_result = await decision_service.run_data_analysis(request_data)
            data_content = self.compose_data_agent_output(request_data, data_result)
            await self.stream_thought(task_id, self.DATA_ROLE, 1, data_content, product_id)
            self.save_or_update_agent_log(db, task_id, product_id, self.DATA_ROLE, 1, data_content)

            market_result = await decision_service.run_market_intel(request_data)
            market_content = self.compose_market_agent_output(request_data, market_result)
            await self.stream_thought(task_id, self.MARKET_ROLE, 2, market_content, product_id)
            self.save_or_update_agent_log(db, task_id, product_id, self.MARKET_ROLE, 2, market_content)

            risk_result = await decision_service.run_risk_control(request_data)
            risk_content = self.compose_risk_agent_output(request_data, risk_result)
            await self.stream_thought(task_id, self.RISK_ROLE, 3, risk_content, product_id)
            self.save_or_update_agent_log(db, task_id, product_id, self.RISK_ROLE, 3, risk_content)

            final_decision = await decision_service.run_manager_decision(
                request_data,
                data_result=data_result,
                market_result=market_result,
                risk_result=risk_result,
            )
            manager_content = self.compose_manager_agent_output(request_data.product.product_name, final_decision)
            await self.stream_thought(task_id, self.MANAGER_ROLE, 4, manager_content, product_id)
            self.save_or_update_agent_log(db, task_id, product_id, self.MANAGER_ROLE, 4, manager_content)

            self.save_result(db, task_id, product_id, final_decision)
            await manager.broadcast(
                json.dumps({"type": "result", "product_id": product_id, "data": final_decision.model_dump()}),
                str(task_id),
            )
        finally:
            db.close()

    def save_or_update_agent_log(self, db: Session, task_id: int, product_id: int, role: str, order: int, content: str):
        try:
            existing_log = (
                db.query(DecAgentLog)
                .filter(
                    DecAgentLog.task_id == task_id,
                    DecAgentLog.role_name == role,
                    DecAgentLog.speak_order == order,
                )
                .first()
            )

            prefixed_content = f"商品 {product_id}\n{content}"
            if existing_log:
                existing_log.thought_content = prefixed_content
            else:
                db.add(
                    DecAgentLog(
                        task_id=task_id,
                        role_name=role,
                        speak_order=order,
                        thought_content=prefixed_content,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Error saving log for role %s on task %s", role, task_id)

    def save_result(self, db: Session, task_id: int, product_id: int, final_decision):
        try:
            existing_result = (
                db.query(DecResult)
                .filter(DecResult.task_id == task_id, DecResult.product_id == product_id)
                .first()
            )

            if existing_result:
                existing_result.decision = final_decision.decision
                existing_result.discount_rate = final_decision.discount_rate
                existing_result.suggested_price = final_decision.suggested_price
                existing_result.profit_change = getattr(
                    getattr(final_decision, "expected_outcomes", None),
                    "profit_change",
                    0.0,
                )
                existing_result.core_reasons = final_decision.core_reasons
            else:
                db.add(
                    DecResult(
                        task_id=task_id,
                        product_id=product_id,
                        decision=final_decision.decision,
                        discount_rate=final_decision.discount_rate,
                        suggested_price=final_decision.suggested_price,
                        profit_change=getattr(
                            getattr(final_decision, "expected_outcomes", None),
                            "profit_change",
                            0.0,
                        ),
                        core_reasons=final_decision.core_reasons,
                        is_accepted=False,
                    )
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Error saving result for task %s product %s", task_id, product_id)

    async def stream_thought(self, task_id: int, role: str, step: int, content: str, product_id: int):
        timestamp = datetime.now().strftime("%H:%M:%S")
        await manager.broadcast(
            json.dumps(
                {
                    "is_stream": True,
                    "is_start": True,
                    "agent_role": role,
                    "step_order": step,
                    "product_id": product_id,
                    "timestamp": timestamp,
                }
            ),
            str(task_id),
        )

        chunk_size = 12
        for index in range(0, len(content), chunk_size):
            await manager.broadcast(
                json.dumps(
                    {
                        "is_stream": True,
                        "agent_role": role,
                        "step_order": step,
                        "product_id": product_id,
                        "thought_content": content[index : index + chunk_size],
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                ),
                str(task_id),
            )
            await asyncio.sleep(0.03)

        await manager.broadcast(
            json.dumps(
                {
                    "is_stream": True,
                    "is_end": True,
                    "agent_role": role,
                    "step_order": step,
                    "product_id": product_id,
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                }
            ),
            str(task_id),
        )

    async def fetch_sales_data(self, db: Session, product_id: int) -> SalesData:
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=90)
            sales_stats = (
                db.query(BizSalesDaily)
                .filter(
                    and_(
                        BizSalesDaily.product_id == product_id,
                        BizSalesDaily.stat_date >= start_date,
                        BizSalesDaily.stat_date <= end_date,
                    )
                )
                .order_by(BizSalesDaily.stat_date)
                .all()
            )

            promotion_history = self.fetch_promotion_history(db, product_id)

            if not sales_stats:
                return SalesData(
                    sales_history_7d=[10] * 7,
                    sales_history_30d=[10] * 30,
                    sales_history_90d=[10] * 90,
                    promotion_history=promotion_history,
                )

            sales_90d = [int(stat.daily_sales or 0) for stat in sales_stats[-90:]]
            sales_30d = sales_90d[-30:]
            sales_7d = sales_90d[-7:]

            while len(sales_7d) < 7:
                sales_7d.insert(0, 0)
            while len(sales_30d) < 30:
                sales_30d.insert(0, 0)
            while len(sales_90d) < 90:
                sales_90d.insert(0, 0)

            return SalesData(
                sales_history_7d=sales_7d,
                sales_history_30d=sales_30d,
                sales_history_90d=sales_90d,
                promotion_history=promotion_history,
            )
        except Exception:
            logger.exception("Error fetching sales data for product %s", product_id)
            return SalesData(
                sales_history_7d=[10] * 7,
                sales_history_30d=[10] * 30,
                sales_history_90d=[10] * 90,
            )

    def fetch_promotion_history(self, db: Session, product_id: int):
        try:
            if self._promotion_history_table_exists is None:
                self._promotion_history_table_exists = inspect(db.get_bind()).has_table("biz_promotion_history")

            if not self._promotion_history_table_exists:
                return []

            promotions = (
                db.query(BizPromotionHistory)
                .filter(BizPromotionHistory.product_id == product_id)
                .order_by(BizPromotionHistory.start_date.desc())
                .limit(5)
                .all()
            )
            return [
                {
                    "date": promo.start_date.isoformat() if promo.start_date else None,
                    "type": promo.promotion_type,
                    "discount_price": float(promo.discount_price) if promo.discount_price is not None else None,
                    "sales_before": int(promo.sales_before or 0),
                    "sales_during": int(promo.sales_during or 0),
                    "sales_lift": float(promo.sales_lift or 0),
                }
                for promo in promotions
            ]
        except Exception:
            logger.exception("Error fetching promotion history for product %s", product_id)
            return []

    async def build_competitor_data(self, product: BizProduct) -> CompetitorData:
        return CompetitorData(competitors=[], upcoming_platform_events=[])

    def parse_constraint_bundle(self, constraints: str) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {
            "raw_text": constraints or "",
            "min_profit_margin": None,
            "min_profit_markup": None,
            "max_discount_allowed": None,
            "price_floor": None,
            "price_ceiling": None,
            "summary": [],
        }

        if not constraints:
            return parsed

        margin_match = re.search(r"(?:毛利率|利润率).*?(?:不低于|不少于|至少|>=?)\s*(\d+(?:\.\d+)?)\s*%", constraints)
        if margin_match:
            parsed["min_profit_margin"] = float(margin_match.group(1)) / 100.0
            parsed["summary"].append(f"毛利率不得低于 {margin_match.group(1)}%")

        markup_match = re.search(r"(?<!毛)(?<!利润率)(?:利润|利润空间|加价率).*?(?:不低于|不少于|至少|>=?)\s*(\d+(?:\.\d+)?)\s*%", constraints)
        if markup_match:
            parsed["min_profit_markup"] = float(markup_match.group(1)) / 100.0
            parsed["summary"].append(f"利润不得低于成本的 {markup_match.group(1)}%")

        discount_match = re.search(
            r"(?:折扣|降价|打折|优惠幅度|降幅).*?(?:不超过|不得超过|最多|上限|不要超过)\s*(\d+(?:\.\d+)?)\s*%",
            constraints,
        )
        if discount_match:
            discount_pct = float(discount_match.group(1))
            parsed["max_discount_allowed"] = max(0.0, 1 - discount_pct / 100.0)
            parsed["summary"].append(f"降价幅度不得超过 {discount_pct:g}%")

        floor_match = re.search(
            r"(?:最低售价|最低价格|售价|价格).*?(?:不低于|不少于|至少|>=?)\s*(\d+(?:\.\d+)?)\s*(?:元|块)?",
            constraints,
        )
        if floor_match:
            parsed["price_floor"] = float(floor_match.group(1))
            parsed["summary"].append(f"售价不得低于 {parsed['price_floor']:.2f} 元")

        ceiling_match = re.search(
            r"(?:最高售价|最高价格|售价|价格).*?(?:不高于|不超过|至多|最多|<=?)\s*(\d+(?:\.\d+)?)\s*(?:元|块)?",
            constraints,
        )
        if ceiling_match:
            parsed["price_ceiling"] = float(ceiling_match.group(1))
            parsed["summary"].append(f"售价不得高于 {parsed['price_ceiling']:.2f} 元")

        return parsed

    async def build_risk_data(self, parsed_constraints: Dict[str, Any], product: BizProduct) -> RiskData:
        min_margin = 0.10
        min_markup = None
        max_discount_allowed = None
        price_floor = None
        price_ceiling = None
        constraint_summary: List[str] = []
        try:
            if parsed_constraints:
                min_margin = parsed_constraints.get("min_profit_margin") or min_margin
                min_markup = parsed_constraints.get("min_profit_markup")
                max_discount_allowed = parsed_constraints.get("max_discount_allowed")
                price_floor = parsed_constraints.get("price_floor")
                price_ceiling = parsed_constraints.get("price_ceiling")
                constraint_summary = parsed_constraints.get("summary", [])

            current_price = float(product.current_price or 0)
            cost_price = float(product.cost_price or 0)
            current_margin = ((current_price - cost_price) / current_price) if current_price > 0 else 0.20

            return RiskData(
                min_profit_margin=min_margin,
                min_profit_markup=min_markup,
                target_profit_margin=max(current_margin, min_margin),
                max_discount_allowed=max_discount_allowed,
                price_floor=price_floor,
                price_ceiling=price_ceiling,
                enforce_hard_constraints=True,
                constraint_summary=constraint_summary,
            )
        except Exception:
            logger.exception("Error building risk data for product %s", product.id)
            return RiskData(min_profit_margin=min_margin, min_profit_markup=min_markup, target_profit_margin=0.20)

    def compose_data_agent_output(self, request: AnalysisRequest, result) -> str:
        sales_30d_avg = sum(request.sales_data.sales_history_30d) / max(len(request.sales_data.sales_history_30d), 1)
        thinking_process = (
            f"我先查看商品 {request.product.product_name} 近 7 天、30 天和 90 天销量走势，"
            f"确认销量趋势为{self.translate_sales_trend(result.sales_trend)}。"
            f"然后结合当前库存 {request.product.stock} 件和预计周转天数 {result.estimated_turnover_days or '未知'} 天，"
            "判断库存压力。"
        )
        reasoning = (
            f"近 30 天日均销量约为 {sales_30d_avg:.1f}，"
            f"库存状态为{self.translate_inventory_status(result.inventory_status)}。"
            f"{'存在历史促销数据，可用于辅助判断折扣弹性。' if request.sales_data.promotion_history else '历史促销数据不足，因此折扣判断更偏保守。'}"
            f"因此我认为 {'需要' if result.recommended_action in {'discount', 'clearance'} else '暂不需要'}通过促销来干预销量。"
        )
        decision = (
            f"建议促销，折扣范围为 {self.format_discount_range(result.recommended_discount_range)}。"
            if result.recommended_action in {'discount', 'clearance'}
            else "暂不建议促销，建议维持当前价格。"
        )

        result.thinking_process = thinking_process
        result.reasoning = reasoning
        result.decision_summary = decision
        return self.format_basic_output(thinking_process, reasoning, decision)

    def compose_market_agent_output(self, request: AnalysisRequest, result) -> str:
        competitor_count = len(request.competitor_data.competitors)
        thinking_process = (
            f"我先比对商品 {request.product.product_name} 的竞品价格和市场活动，"
            f"当前竞品样本数为 {competitor_count}，"
            f"价格定位为{self.translate_price_position(result.price_position)}，"
            f"竞争强度为{self.translate_competition_level(result.competition_level)}。"
        )
        reasoning = (
            f"平均竞品价格为 {result.avg_competitor_price or 0:.2f}，"
            f"本商品相对均价差异为 {((result.price_gap_vs_avg or 0) * 100):.1f}%。"
            f"市场建议为{self.translate_market_suggestion(result.market_suggestion)}。"
            f"主要原因是 {self.join_sentences(result.suggestion_reasons[:3], '竞品价格和市场活动共同推动了该判断。')}"
        )
        decision = (
            f"建议{'参与促销' if result.market_suggestion in {'price_war', 'penetrate', 'discount'} else '暂不跟进促销'}，"
            f"市场策略为{self.translate_market_suggestion(result.market_suggestion)}。"
        )

        result.thinking_process = thinking_process
        result.reasoning = reasoning
        result.decision_summary = decision
        return self.format_basic_output(thinking_process, reasoning, decision)

    def compose_risk_agent_output(self, request: AnalysisRequest, result) -> str:
        discount_margin = (
            result.profit_margin_after_discount
            if result.profit_margin_after_discount is not None
            else result.current_profit_margin
        )
        veto_reason = self.clean_sentence_tail(result.veto_reason or "风险超过阈值")
        constraint_text = self.join_sentences(
            result.constraint_summary[:2],
            f"最低可执行价格为 {result.required_min_price:.2f} 元",
        )
        thinking_process = (
            f"我先计算商品 {request.product.product_name} 当前毛利率 {result.current_profit_margin:.1%}，"
            f"再推算折后毛利率 {discount_margin:.1%}，"
            "同时检查利润红线、库存风险和合规风险。"
        )
        reasoning = (
            f"当前风险等级为{self.translate_risk_level(result.risk_level)}，"
            f"最低安全价格为 {result.min_safe_price:.2f}，"
            f"最大安全价格系数为 {result.max_safe_discount:.2f}。"
            f"约束结论为 {constraint_text}"
            f"{'风险控制允许促销。' if result.allow_promotion else f'风险控制不允许促销，原因是 {veto_reason}。'}"
        )
        if not result.current_price_compliant:
            decision = f"当前价格不满足约束，建议至少调整到 {result.required_min_price:.2f} 元。"
        elif result.allow_promotion:
            decision = f"允许促销，安全折扣区间为 {self.format_safe_discount_range(result.max_safe_discount)}。"
        else:
            decision = "不允许促销，建议维持当前价格。"

        result.thinking_process = thinking_process
        result.reasoning = reasoning
        result.decision_summary = decision
        return self.format_basic_output(thinking_process, reasoning, decision)

    def compose_manager_agent_output(self, product_name: str, result) -> str:
        sections = [
            "思考过程：",
            f"商品 {product_name}。{result.thinking_process}",
            "",
            "分析理由：",
            result.reasoning,
            "",
            "核心依据：",
            result.core_reasons,
        ]
        if result.conflict_summary:
            sections.extend(["", "冲突处理：", result.conflict_summary])
        sections.extend(
            [
                "",
                "最终决定：",
                (
                    f"建议维持现价，建议价格为 {result.suggested_price:.2f}。"
                    if result.decision == "maintain"
                    else f"建议提价，建议价格为 {result.suggested_price:.2f}。"
                    if result.decision == "increase"
                    else f"建议执行 {self.format_single_discount(result.discount_rate)}，建议价格为 {result.suggested_price:.2f}。"
                ),
            ]
        )
        return "\n".join(sections)

    def format_basic_output(self, thinking_process: str, reasoning: str, decision: str) -> str:
        return "\n".join(
            [
                "思考过程：",
                thinking_process,
                "",
                "分析理由：",
                reasoning,
                "",
                "最终决定：",
                decision,
            ]
        )

    def join_sentences(self, values: List[str], fallback: str) -> str:
        cleaned = [self.clean_sentence_tail(value) for value in values if value and value.strip()]
        if not cleaned:
            normalized_fallback = self.clean_sentence_tail(fallback)
            return f"{normalized_fallback}。" if normalized_fallback else ""
        return "；".join(cleaned) + "。"

    def clean_sentence_tail(self, value: str) -> str:
        return value.strip().rstrip("。；;，,")

    def translate_sales_trend(self, value: str) -> str:
        mapping = {
            "rapid_rising": "快速上升",
            "rising": "上升",
            "stable": "稳定",
            "declining": "下降",
            "rapid_declining": "快速下降",
        }
        return mapping.get(value, value)

    def translate_inventory_status(self, value: str) -> str:
        mapping = {
            "severe_overstock": "严重积压",
            "overstock": "积压",
            "normal": "正常",
            "tight": "偏紧",
            "shortage": "短缺",
        }
        return mapping.get(value, value)

    def translate_competition_level(self, value: str) -> str:
        mapping = {"fierce": "高", "moderate": "中", "low": "低"}
        return mapping.get(value, value)

    def translate_price_position(self, value: str) -> str:
        mapping = {"premium": "偏高", "mid-range": "居中", "budget": "偏低"}
        return mapping.get(value, value)

    def translate_market_suggestion(self, value: str) -> str:
        mapping = {
            "price_war": "建议跟进促销",
            "penetrate": "建议主动压价",
            "discount": "建议短期促销",
            "differentiate": "建议差异化竞争",
            "premium": "建议尝试提价",
            "maintain": "建议维持现价",
        }
        return mapping.get(value, value)

    def translate_risk_level(self, value: str) -> str:
        mapping = {"high": "高", "medium": "中", "low": "低"}
        return mapping.get(value, value)

    def format_discount_range(self, rate_range) -> str:
        low_off = round((1 - rate_range[1]) * 100)
        high_off = round((1 - rate_range[0]) * 100)
        if low_off == high_off:
            return f"{low_off}%"
        return f"{low_off}%-{high_off}%"

    def format_safe_discount_range(self, min_rate: float) -> str:
        return f"0%-{round((1 - min_rate) * 100)}%"

    def format_single_discount(self, rate: float) -> str:
        if rate >= 1.0:
            return "不打折"
        return f"{rate * 10:.1f} 折"


workflow_service = WorkflowService()
