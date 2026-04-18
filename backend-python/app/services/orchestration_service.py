"""
定价决策编排服务（CrewAI 版）
============================
使用 CrewAI Crew 驱动 4 个 Agent 顺序执行定价决策。
每个 Task 完成时通过回调将 Agent 卡片实时写入数据库，
前端通过 Java 实时流读取 agent_run_log 表即可展示进度。

执行流程：
  1. 构建 LLM 实例
  2. 构建 Crew（4 Agent + 4 Task，顺序执行）
  3. crew.kickoff() 启动执行
  4. 每个 Task 完成 → callback → 解析 LLM 输出 → 写入 agent_run_log
  5. 最终 Task 完成后 → 解析经理决策 → 强制硬约束校验 → 写入 pricing_result
"""

import logging
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crew.crew_factory import build_pricing_crew
from app.crew.crewai_runtime import build_crewai_llm, debug_log, extract_json_object
from app.crew.protocols import CrewRunPayload
from app.schemas.agent import DataAgentOutput, ManagerAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.schemas.result import TaskFinalResult
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, to_strategy_goal_cn, to_risk_level_cn

logger = logging.getLogger(__name__)


def _safe_float(val: Any, default: float = 0.0) -> float:
    """安全地将 LLM 返回的值转换为 float，避免非数字值导致崩溃。"""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """安全地将 LLM 返回的值转换为 int。"""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


# ── Agent 元数据（名称和展示顺序） ──────────────────────────
_AGENT_META = [
    {"code": "DATA_ANALYSIS", "name": "数据分析Agent", "order": 1},
    {"code": "MARKET_INTEL", "name": "市场情报Agent", "order": 2},
    {"code": "RISK_CONTROL", "name": "风险控制Agent", "order": 3},
    {"code": "MANAGER_COORDINATOR", "name": "经理协调Agent", "order": 4},
]

_AGENT_OUTPUT_MODELS = {
    "DATA_ANALYSIS": DataAgentOutput,
    "MARKET_INTEL": MarketAgentOutput,
    "RISK_CONTROL": RiskAgentOutput,
    "MANAGER_COORDINATOR": ManagerAgentOutput,
}


class AgentOutputValidationError(RuntimeError):
    def __init__(self, agent_code: str, message: str):
        super().__init__(message)
        self.agent_code = agent_code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.agent_code}] {self.message}"


class OrchestrationService:
    """4-Agent CrewAI 编排服务：通过 LLM 驱动的多Agent协作完成定价决策。"""

    def __init__(self, db: Session):
        self.db = db
        self.log_tool = LogWriterTool(db)
        self.result_tool = ResultWriterTool(db)

    @staticmethod
    def _summarize_failure_message(error: Any) -> str:
        text = str(error or "").strip()
        normalized = text.lower()
        if not text:
            return "CrewAI 任务执行失败"

        agent_timeout_tokens = ("execution timed out", "max_execution_time")
        if any(token in normalized for token in agent_timeout_tokens):
            return "Agent 执行超时"

        timeout_tokens = ("timeout", "timed out", "time out", "readtimeout", "connecttimeout")
        if any(token in normalized for token in timeout_tokens):
            return "LLM 调用超时"

        parse_tokens = ("json", "parse", "decode", "expecting value", "invalid control character")
        if any(token in normalized for token in parse_tokens):
            return "输出解析失败"

        return "CrewAI 任务执行失败"

    @staticmethod
    def _build_failed_card(summary: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        concise = str(summary or "").strip() or "CrewAI 任务执行失败"
        return (
            concise,
            [{"label": "错误摘要", "value": concise}],
            {"error": True, "message": concise},
        )

    @staticmethod
    def _validate_agent_output(agent_code: str, parsed: dict[str, Any]) -> dict[str, Any]:
        model_cls = _AGENT_OUTPUT_MODELS.get(agent_code)
        if model_cls is None:
            return parsed
        try:
            model = model_cls.model_validate(parsed)
        except ValidationError as exc:
            raise AgentOutputValidationError(agent_code, "输出结构校验失败") from exc
        return model.model_dump(by_alias=True, exclude_none=True)

    # ── 从 LLM 输出构建数据分析卡片 ──────────────────────────
    @staticmethod
    def _build_data_card(
        payload: CrewRunPayload,
        parsed: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        """
        将数据分析 Agent 的 LLM 输出解析为前端展示的卡片格式。
        返回: (thinking摘要, evidence列表, suggestion字典)
        """
        # thinking: LLM 的分析思路概述
        thinking = parsed.get("thinking", "基于商品经营数据评估价格弹性与利润-销量关系，给出数据驱动的建议价格区间。")

        # evidence: 支撑决策的关键数据点
        evidence = [
            {"label": "策略目标", "value": to_strategy_goal_cn(payload.strategy_goal)},
            {"label": "基线销量(月)", "value": int(payload.baseline_sales)},
            {"label": "基线利润(月)", "value": float(money(payload.baseline_profit))},
            {"label": "当前售价", "value": float(money(payload.product.current_price))},
            {"label": "成本价", "value": float(money(payload.product.cost_price))},
        ]

        # suggestion: Agent 的定价建议
        suggested_price = _safe_float(parsed.get("suggestedPrice"))
        min_price = _safe_float(parsed.get("suggestedMinPrice"))
        max_price = _safe_float(parsed.get("suggestedMaxPrice"))
        expected_sales = _safe_int(parsed.get("expectedSales"))
        expected_profit = _safe_float(parsed.get("expectedProfit"))

        suggestion = {
            "priceRange": {"min": min_price, "max": max_price},
            "recommendedPrice": suggested_price,
            "expectedSales": expected_sales,
            "expectedProfit": expected_profit,
            "expectedProfitRate": round(
                expected_profit / max(suggested_price * max(expected_sales, 1), 0.01), 4
            ),
            "summary": parsed.get("summary", "数据分析完成"),
        }

        return thinking, evidence, suggestion

    # ── 从 LLM 输出构建市场情报卡片 ──────────────────────────
    @staticmethod
    def _build_market_card(
        parsed: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        """
        将市场情报 Agent 的 LLM 输出解析为前端展示的卡片格式。
        """
        thinking = parsed.get("thinking", "基于竞品价格数据分析市场价格带和竞争态势，给出市场可接受的建议价格。")

        # 从 LLM 输出中提取竞品样本数
        sample_count = _safe_int(parsed.get("competitorSamples"))
        raw_count = _safe_int(parsed.get("rawItemCount", sample_count))
        filtered_count = _safe_int(parsed.get("filteredItemCount", sample_count))
        market_floor = _safe_float(parsed.get("marketFloor"))
        market_median = _safe_float(parsed.get("marketMedian"))
        market_ceiling = _safe_float(parsed.get("marketCeiling"))
        market_average = _safe_float(parsed.get("marketAverage"))
        valid_count = _safe_int(parsed.get("usedCompetitorCount", parsed.get("validCompetitorCount", sample_count)))
        source = str(parsed.get("source", "UNKNOWN"))
        source_status = str(parsed.get("sourceStatus", "UNKNOWN"))
        data_quality = str(parsed.get("dataQuality", "LOW"))
        quality_reasons = parsed.get("qualityReasons")
        pricing_position = str(parsed.get("pricingPosition", "")).strip()
        evidence_summary = str(parsed.get("evidenceSummary", "")).strip()

        risk_notes = parsed.get("riskNotes")
        degraded = source_status.upper() != "OK" or data_quality.upper() == "LOW" or valid_count < 3
        if not risk_notes and degraded:
            risk_notes = "本次竞品数据不足，仅供参考"

        evidence = [
            {"label": "原始样本数", "value": raw_count},
            {"label": "过滤后样本数", "value": filtered_count},
            {"label": "竞品样本数", "value": sample_count},
            {"label": "有效样本数", "value": valid_count},
            {"label": "市场最低价", "value": market_floor},
            {"label": "市场中位价", "value": market_median},
            {"label": "市场最高价", "value": market_ceiling},
            {"label": "市场均价", "value": market_average},
        ]

        evidence.extend(
            [
                {"label": "竞品来源", "value": source},
                {"label": "竞品状态", "value": source_status},
                {"label": "数据质量", "value": data_quality},
            ]
        )

        sales_weighted_avg = _safe_float(parsed.get("salesWeightedAverage"))
        sales_weighted_median = _safe_float(parsed.get("salesWeightedMedian"))
        if sales_weighted_avg is not None:
            evidence.append({"label": "销量加权均价", "value": sales_weighted_avg})
        if sales_weighted_median is not None:
            evidence.append({"label": "销量加权中位价", "value": sales_weighted_median})

        brand_breakdown = parsed.get("brandBreakdown") or []
        if isinstance(brand_breakdown, list) and brand_breakdown:
            evidence.append({"label": "品牌价格带", "value": brand_breakdown[:5]})

        shop_type_breakdown = parsed.get("shopTypeBreakdown") or []
        if isinstance(shop_type_breakdown, list) and shop_type_breakdown:
            evidence.append({"label": "店铺类型分布", "value": shop_type_breakdown[:5]})

        promotion_density = parsed.get("promotionDensity") or {}
        if isinstance(promotion_density, dict) and promotion_density:
            evidence.append({"label": "促销密度", "value": promotion_density})

        if quality_reasons:
            evidence.append({"label": "质量原因", "value": quality_reasons})
        if evidence_summary:
            evidence.append({"label": "证据摘要", "value": evidence_summary})

        suggestion = {
            "priceRange": {"min": market_floor, "max": market_ceiling},
            "recommendedPrice": float(parsed.get("suggestedPrice", 0)),
            "marketScore": round(float(parsed.get("confidence", 0.5)) * 100, 2),
            "source": source,
            "sourceStatus": source_status,
            "dataQuality": data_quality,
            "pricingPosition": pricing_position,
            "usedCompetitorCount": valid_count,
            "riskNotes": risk_notes,
            "evidenceSummary": evidence_summary or None,
            "salesWeightedAverage": sales_weighted_avg,
            "summary": parsed.get("summary", "市场情报分析完成"),
        }

        return thinking, evidence, suggestion

    # ── 从 LLM 输出构建风控卡片 ──────────────────────────────
    @staticmethod
    def _build_risk_card(
        payload: CrewRunPayload,
        parsed: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        """
        将风险控制 Agent 的 LLM 输出解析为前端展示的卡片格式。
        """
        thinking = parsed.get("thinking", "对候选价格执行成本底线与利润约束校验，判断是否允许自动执行。")

        is_pass = bool(parsed.get("isPass", False))
        safe_floor = _safe_float(parsed.get("safeFloorPrice"))
        suggested = _safe_float(parsed.get("suggestedPrice"))
        risk_level = str(parsed.get("riskLevel", "HIGH"))

        evidence = [
            {"label": "风控建议价", "value": suggested},
            {"label": "安全底价", "value": safe_floor},
            {"label": "基线利润(月)", "value": float(money(payload.baseline_profit))},
            {"label": "硬约束通过", "value": is_pass},
        ]

        suggestion = {
            "recommendedPrice": suggested,
            "pass": is_pass,
            "riskLevel": to_risk_level_cn(risk_level),
            "action": "自动执行" if is_pass else "人工审核",
            "summary": parsed.get("summary", "风控评估完成"),
        }

        return thinking, evidence, suggestion

    # ── 从 LLM 输出构建经理协调卡片 ──────────────────────────
    @staticmethod
    def _build_manager_card(
        parsed: dict[str, Any],
        data_parsed: dict[str, Any],
        market_parsed: dict[str, Any],
        risk_parsed: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any], str]:
        """
        将经理协调 Agent 的 LLM 输出解析为前端展示的卡片格式。
        返回: (thinking, evidence, suggestion, reason_why)
        """
        thinking = parsed.get("thinking", "综合前三个Agent的意见，输出最终可执行的定价决策。")

        evidence = [
            {"label": "数据分析建议价", "value": _safe_float(data_parsed.get("suggestedPrice"))},
            {"label": "市场情报建议价", "value": _safe_float(market_parsed.get("suggestedPrice"))},
            {"label": "风险控制建议价", "value": _safe_float(risk_parsed.get("suggestedPrice"))},
            {"label": "风控通过", "value": bool(risk_parsed.get("isPass", False))},
        ]

        suggestion = {
            "finalPrice": _safe_float(parsed.get("finalPrice")),
            "expectedSales": _safe_int(parsed.get("expectedSales")),
            "expectedProfit": _safe_float(parsed.get("expectedProfit")),
            "strategy": MANUAL_REVIEW_STRATEGY,
            "summary": parsed.get("resultSummary", "综合决策完成"),
        }

        # 决策理由：优先使用 LLM 生成的摘要
        reason_why = str(parsed.get("resultSummary", "综合数据、市场、风控意见给出最终建议价格。"))

        return thinking, evidence, suggestion, reason_why

    # ── 主执行方法 ────────────────────────────────────────────
    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        """
        使用 CrewAI Crew 驱动 4 个 Agent 顺序执行定价决策。

        流程：
          1. 构建 LLM → 构建 Crew
          2. crew.kickoff() 执行（每个 Task 完成后回调写入卡片）
          3. 解析最终输出 → 强制硬约束 → 写入结果
        """
        # ── 构建 CrewAI LLM 实例 ──────────────────────────────
        analysis_llm = build_crewai_llm(
            profile="fast",
            api_key=payload.llm_api_key,
            base_url=payload.llm_base_url,
            model=payload.llm_model,
        )
        manager_llm = build_crewai_llm(
            profile="default",
            api_key=payload.llm_api_key,
            base_url=payload.llm_base_url,
            model=payload.llm_model,
        )
        logger.info(
            "CrewAI LLMs built analysis_model=%s manager_model=%s",
            analysis_llm.model,
            manager_llm.model,
        )
        debug_log(
            "[CrewAI] llms built "
            f"analysis_model={analysis_llm.model} manager_model={manager_llm.model} "
            f"task_id={payload.task_id}"
        )

        # ── 用于收集每个 Task 的解析结果 ──────────────────────
        task_outputs: list[dict[str, Any]] = []
        validation_errors: list[AgentOutputValidationError] = []
        card_counter = [0]  # 使用列表以便在闭包中修改

        def write_next_running_card(completed_idx: int) -> None:
            next_idx = completed_idx + 1
            if next_idx >= len(_AGENT_META):
                return
            next_meta = _AGENT_META[next_idx]
            self.log_tool.write_running_card(
                task_id=payload.task_id,
                agent_name=next_meta["name"],
                display_order=next_meta["order"],
            )

        def on_task_done(task_output: Any) -> None:
            """
            Task 完成时的回调函数。
            解析 LLM 输出，构建 Agent 卡片，写入数据库。
            这是实现实时结果推送的关键: 每个 Task 完成后立即入库。
            """
            try:
                # 获取 LLM 原始输出并解析 JSON
                raw = str(task_output.raw) if hasattr(task_output, "raw") else str(task_output)
                debug_log(f"[CrewAI] task callback raw_len={len(raw)} raw_preview={raw[:200]}")
                parsed = extract_json_object(raw)

                # 确定当前是第几个 Agent
                idx = card_counter[0]
                card_counter[0] += 1

                if idx >= len(_AGENT_META):
                    logger.warning("回调次数超过预期 Agent 数量: idx=%d", idx)
                    task_outputs.append(parsed)
                    return

                meta = _AGENT_META[idx]

                # 空输出保护：写入错误卡片而非全零卡片
                if not parsed:
                    exc = AgentOutputValidationError(meta["code"], "输出解析失败")
                    validation_errors.append(exc)
                    logger.warning("Agent [%s] 输出解析失败，写入错误卡片", meta["name"])
                    task_outputs.append({})
                    thinking, evidence, suggestion = self._build_failed_card(str(exc))
                    self.log_tool.write_agent_card(
                        task_id=payload.task_id,
                        agent_name=meta["name"],
                        display_order=meta["order"],
                        thinking_summary=thinking,
                        evidence=evidence,
                        suggestion=suggestion,
                        stage="failed",
                    )
                    write_next_running_card(idx)
                    return

                try:
                    parsed = self._validate_agent_output(meta["code"], parsed)
                except AgentOutputValidationError as exc:
                    validation_errors.append(exc)
                    task_outputs.append({})
                    logger.warning("Agent [%s] 输出结构校验失败: %s", meta["name"], exc, exc_info=True)
                    thinking, evidence, suggestion = self._build_failed_card(str(exc))
                    self.log_tool.write_agent_card(
                        task_id=payload.task_id,
                        agent_name=meta["name"],
                        display_order=meta["order"],
                        thinking_summary=thinking,
                        evidence=evidence,
                        suggestion=suggestion,
                        stage="failed",
                    )
                    write_next_running_card(idx)
                    return

                task_outputs.append(parsed)
                logger.info("Agent [%s] 完成，正在写入卡片 (order=%d)", meta["name"], meta["order"])

                # 根据 Agent 类型构建不同格式的卡片
                if idx == 0:
                    # 数据分析Agent
                    thinking, evidence, suggestion = self._build_data_card(payload, parsed)
                    reason_why = None
                elif idx == 1:
                    # 市场情报Agent
                    thinking, evidence, suggestion = self._build_market_card(parsed)
                    reason_why = None
                elif idx == 2:
                    # 风险控制Agent
                    thinking, evidence, suggestion = self._build_risk_card(payload, parsed)
                    reason_why = None
                else:
                    # 经理协调Agent
                    data_p = task_outputs[0] if len(task_outputs) > 0 else {}
                    market_p = task_outputs[1] if len(task_outputs) > 1 else {}
                    risk_p = task_outputs[2] if len(task_outputs) > 2 else {}
                    thinking, evidence, suggestion, reason_why = self._build_manager_card(
                        parsed, data_p, market_p, risk_p
                    )

                # 写入 agent_run_log 表，立即 commit 后前端即可通过实时流看到更新
                self.log_tool.write_agent_card(
                    task_id=payload.task_id,
                    agent_name=meta["name"],
                    display_order=meta["order"],
                    thinking_summary=thinking,
                    evidence=evidence,
                    suggestion=suggestion,
                    reason_why=reason_why,
                )
                logger.info("Agent [%s] 卡片已写入数据库", meta["name"])
                write_next_running_card(idx)

            except Exception as exc:
                # 回调异常不应中断 Crew 执行
                logger.error("写入 Agent 卡片失败: %s", exc, exc_info=True)
                debug_log(f"[CrewAI] write card failed error={exc}")

        # ── 构建并执行 Crew ────────────────────────────────────
        logger.info("开始构建定价 Crew (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] building crew task_id={payload.task_id}")
        crew = build_pricing_crew(
            payload=payload,
            analysis_llm=analysis_llm,
            manager_llm=manager_llm,
            on_task_done=on_task_done,
        )

        first_meta = _AGENT_META[0]
        self.log_tool.write_running_card(
            task_id=payload.task_id,
            agent_name=first_meta["name"],
            display_order=first_meta["order"],
        )
        logger.info("Crew 启动执行 (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] crew kickoff task_id={payload.task_id}")
        try:
            crew_output = crew.kickoff()
        except Exception as crew_exc:
            # Crew 执行失败：为第一个未完成的 Agent 写入错误卡片，
            # 让前端实时流能尽快拿到错误信息，而不是一直停留在加载中
            logger.error("Crew 执行失败: %s", crew_exc, exc_info=True)
            debug_log(f"[CrewAI] crew kickoff failed error={crew_exc}")
            error_idx = card_counter[0]  # 当前未完成的 Agent 索引
            if error_idx < len(_AGENT_META):
                meta = _AGENT_META[error_idx]
                summary = self._summarize_failure_message(crew_exc)
                thinking, evidence, suggestion = self._build_failed_card(summary)
                self.log_tool.write_agent_card(
                    task_id=payload.task_id,
                    agent_name=meta["name"],
                    display_order=meta["order"],
                    thinking_summary=thinking,
                    evidence=evidence,
                    suggestion=suggestion,
                    stage="failed",
                )
                debug_log(f"[CrewAI] wrote error card agent={meta['name']}")
            if validation_errors:
                raise validation_errors[0] from crew_exc
            raise  # 继续向上抛出，让 dispatch_service 标记 task 为 FAILED

        logger.info("Crew 执行完成 (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] crew completed task_id={payload.task_id}")

        if validation_errors:
            raise validation_errors[0]

        # ── 解析最终经理决策 ──────────────────────────────────
        # 从最后一个 Task 的输出中提取最终定价结果
        raw_final = str(crew_output) if crew_output else ""
        manager_parsed = extract_json_object(raw_final)

        # 如果 kickoff 输出解析失败，回退到 callback 收集的经理 Agent 结果
        if not manager_parsed and len(task_outputs) >= 4:
            manager_parsed = task_outputs[3]
            logger.info("使用经理 Agent 回调输出作为回退 (task_id=%d)", payload.task_id)
        elif not manager_parsed:
            logger.warning("经理 Agent 输出不可用，仅 %d 个 Agent 完成 (task_id=%d)", len(task_outputs), payload.task_id)
            manager_parsed = {}

        manager_parsed = self._validate_agent_output("MANAGER_COORDINATOR", manager_parsed)

        # 提取最终定价字段。核心字段必须来自已校验的经理 Agent 输出，不再静默兜底。
        final_price = money(manager_parsed["finalPrice"])
        expected_sales = int(manager_parsed["expectedSales"])
        expected_profit = money(manager_parsed["expectedProfit"])
        profit_growth = money(expected_profit - money(payload.baseline_profit))
        execute_strategy = MANUAL_REVIEW_STRATEGY
        is_pass = bool(manager_parsed["isPass"])
        result_summary = str(manager_parsed["resultSummary"])

        # 提取建议价格区间
        suggested_min = money(manager_parsed["suggestedMinPrice"])
        suggested_max = money(manager_parsed["suggestedMaxPrice"])

        # ── 强制硬约束校验（Python 代码强制执行，不依赖 LLM 判断） ──
        # 约束1: 最终价格不得低于成本价（不允许亏损）
        cost = money(payload.product.cost_price)
        if final_price < cost:
            logger.warning("硬约束: 最终价格 %s 低于成本价 %s，强制标记为人工审核", final_price, cost)
            is_pass = False
            execute_strategy = MANUAL_REVIEW_STRATEGY

        # 约束2: 预期利润必须高于基线利润（调价必须有意义）
        if expected_profit <= money(payload.baseline_profit):
            logger.warning(
                "硬约束: 预期利润 %s 未超过基线利润 %s，强制标记为人工审核",
                expected_profit,
                money(payload.baseline_profit),
            )
            is_pass = False
            execute_strategy = MANUAL_REVIEW_STRATEGY

        # ── 构建并写入最终定价结果 ──────────────────────────────
        final_payload = TaskFinalResult(
            taskId=payload.task_id,
            finalPrice=final_price,
            expectedSales=expected_sales,
            expectedProfit=expected_profit,
            profitGrowth=profit_growth,
            isPass=is_pass,
            executeStrategy=execute_strategy,
            resultSummary=result_summary,
            suggestedMinPrice=suggested_min,
            suggestedMaxPrice=suggested_max,
        )
        self.result_tool.write_final_result(final_payload)
        logger.info(
            "定价结果已写入: task_id=%d, final_price=%s, strategy=%s",
            payload.task_id,
            final_price,
            execute_strategy,
        )

        return final_payload
