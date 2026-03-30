"""
定价决策编排服务（CrewAI 版）
============================
使用 CrewAI Crew 驱动 4 个 Agent 顺序执行定价决策。
每个 Task 完成时通过回调将 Agent 卡片实时写入数据库，
前端 WebSocket 轮询 agent_run_log 表即可展示实时进度。

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

from sqlalchemy.orm import Session

from app.crew.crew_factory import build_pricing_crew
from app.crew.crewai_runtime import build_crewai_llm, extract_json_object
from app.crew.protocols import CrewRunPayload
from app.schemas.result import TaskFinalResult
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool
from app.utils.math_utils import money
from app.utils.text_utils import to_strategy_goal_cn, to_risk_level_cn

logger = logging.getLogger(__name__)

# ── Agent 元数据（名称和展示顺序） ──────────────────────────
_AGENT_META = [
    {"code": "DATA_ANALYSIS", "name": "数据分析Agent", "order": 1},
    {"code": "MARKET_INTEL", "name": "市场情报Agent", "order": 2},
    {"code": "RISK_CONTROL", "name": "风险控制Agent", "order": 3},
    {"code": "MANAGER_COORDINATOR", "name": "经理协调Agent", "order": 4},
]


class OrchestrationService:
    """4-Agent CrewAI 编排服务：通过 LLM 驱动的多Agent协作完成定价决策。"""

    def __init__(self, db: Session):
        self.db = db
        self.log_tool = LogWriterTool(db)
        self.result_tool = ResultWriterTool(db)

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
        suggested_price = float(parsed.get("suggestedPrice", 0))
        min_price = float(parsed.get("suggestedMinPrice", 0))
        max_price = float(parsed.get("suggestedMaxPrice", 0))
        expected_sales = int(parsed.get("expectedSales", 0))
        expected_profit = float(parsed.get("expectedProfit", 0))
        confidence = float(parsed.get("confidence", 0.5))

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
        sample_count = int(parsed.get("simulatedSamples", 0))
        market_floor = float(parsed.get("marketFloor", 0))
        market_ceiling = float(parsed.get("marketCeiling", 0))

        evidence = [
            {"label": "竞品样本数", "value": sample_count},
            {"label": "市场最低价", "value": market_floor},
            {"label": "市场最高价", "value": market_ceiling},
        ]

        suggestion = {
            "priceRange": {"min": market_floor, "max": market_ceiling},
            "recommendedPrice": float(parsed.get("suggestedPrice", 0)),
            "marketScore": round(float(parsed.get("confidence", 0.5)) * 100, 2),
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
        safe_floor = float(parsed.get("safeFloorPrice", 0))
        suggested = float(parsed.get("suggestedPrice", 0))
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
            {"label": "数据分析建议价", "value": float(data_parsed.get("suggestedPrice", 0))},
            {"label": "市场情报建议价", "value": float(market_parsed.get("suggestedPrice", 0))},
            {"label": "风险控制建议价", "value": float(risk_parsed.get("suggestedPrice", 0))},
            {"label": "风控通过", "value": bool(risk_parsed.get("isPass", False))},
        ]

        suggestion = {
            "finalPrice": float(parsed.get("finalPrice", 0)),
            "expectedSales": int(parsed.get("expectedSales", 0)),
            "expectedProfit": float(parsed.get("expectedProfit", 0)),
            "strategy": str(parsed.get("executeStrategy", "人工审核")),
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
        llm = build_crewai_llm()
        logger.info("CrewAI LLM 已构建: model=%s, base_url=%s", llm.model, llm.base_url)

        # ── 用于收集每个 Task 的解析结果 ──────────────────────
        task_outputs: list[dict[str, Any]] = []
        card_counter = [0]  # 使用列表以便在闭包中修改

        def on_task_done(task_output: Any) -> None:
            """
            Task 完成时的回调函数。
            解析 LLM 输出，构建 Agent 卡片，写入数据库。
            这是实现 WebSocket 实时推送的关键——每个 Task 完成后立即入库。
            """
            try:
                # 获取 LLM 原始输出并解析 JSON
                raw = str(task_output.raw) if hasattr(task_output, "raw") else str(task_output)
                parsed = extract_json_object(raw)
                task_outputs.append(parsed)

                # 确定当前是第几个 Agent
                idx = card_counter[0]
                card_counter[0] += 1

                if idx >= len(_AGENT_META):
                    logger.warning("回调次数超过预期 Agent 数量: idx=%d", idx)
                    return

                meta = _AGENT_META[idx]
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

                # 写入 agent_run_log 表（立即 commit，WebSocket 轮询可即时读取）
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

            except Exception as exc:
                # 回调异常不应中断 Crew 执行
                logger.error("写入 Agent 卡片失败: %s", exc, exc_info=True)

        # ── 构建并执行 Crew ────────────────────────────────────
        logger.info("开始构建定价 Crew (task_id=%d)", payload.task_id)
        crew = build_pricing_crew(payload=payload, llm=llm, on_task_done=on_task_done)

        logger.info("Crew 启动执行 (task_id=%d)", payload.task_id)
        crew_output = crew.kickoff()
        logger.info("Crew 执行完成 (task_id=%d)", payload.task_id)

        # ── 解析最终经理决策 ──────────────────────────────────
        # 从最后一个 Task 的输出中提取最终定价结果
        raw_final = str(crew_output) if crew_output else ""
        manager_parsed = extract_json_object(raw_final)

        # 如果 kickoff 输出解析失败，回退到 callback 收集的最后一个结果
        if not manager_parsed and task_outputs:
            manager_parsed = task_outputs[-1]

        # 提取最终定价字段（带默认值兜底）
        final_price = money(manager_parsed.get("finalPrice", payload.product.current_price))
        expected_sales = int(manager_parsed.get("expectedSales", payload.baseline_sales))
        expected_profit = money(manager_parsed.get("expectedProfit", payload.baseline_profit))
        profit_growth = money(expected_profit - money(payload.baseline_profit))
        execute_strategy = str(manager_parsed.get("executeStrategy", "人工审核"))
        is_pass = bool(manager_parsed.get("isPass", False))
        result_summary = str(manager_parsed.get("resultSummary", "定价决策完成"))

        # 提取建议价格区间
        suggested_min = money(manager_parsed.get("suggestedMinPrice", final_price * Decimal("0.95")))
        suggested_max = money(manager_parsed.get("suggestedMaxPrice", final_price * Decimal("1.05")))

        # ── 强制硬约束校验（Python 代码强制执行，不依赖 LLM 判断） ──
        # 约束1: 最终价格不得低于成本价（不允许亏损）
        cost = money(payload.product.cost_price)
        if final_price < cost:
            logger.warning("硬约束: 最终价格 %s 低于成本价 %s，强制标记为人工审核", final_price, cost)
            is_pass = False
            execute_strategy = "人工审核"

        # 约束2: 预期利润必须高于基线利润（调价必须有意义）
        if expected_profit <= money(payload.baseline_profit):
            logger.warning(
                "硬约束: 预期利润 %s 未超过基线利润 %s，强制标记为人工审核",
                expected_profit,
                money(payload.baseline_profit),
            )
            is_pass = False
            execute_strategy = "人工审核"

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
