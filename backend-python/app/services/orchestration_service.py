"""
定价决策编排服务（CrewAI 版）
============================
驱动 4 个 CrewAI Agent 按顺序执行定价决策，支持 Agent 粒度的失败重试。

执行流程：
  1. 构建 LLM 实例
  2. 构建 CrewBundle（4 Agent + 4 Task）
  3. 通过 ResumeService 计算续跑断点（上一轮已完成的 Agent 会被跳过）
  4. 对每个需要执行的 Task 手动调用 task.execute_sync
     - 已完成的 Agent：从 agent_run_log.raw_output_json 读取输出 → 作为 context 注入
     - 失败/未开始的 Agent：真正调用 LLM 执行
  5. 每个 Agent 成功后立即写入 agent_run_log（带 raw_output_json）供下次重试复用
  6. 经理 Agent 完成后 → 解析最终决策 → 强制硬约束校验 → 写入 pricing_result
"""

import json
import logging
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crew.crew_factory import CrewBundle, build_pricing_crew
from app.crew.crewai_runtime import build_crewai_llm, debug_log, extract_json_object
from app.crew.protocols import CrewRunPayload
from app.schemas.agent import DataAgentOutput, ManagerAgentOutput, MarketAgentOutput, RiskAgentOutput
from app.schemas.result import TaskFinalResult
from app.services.resume_service import ResumeService
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


def _safe_positive_float(val: Any) -> float | None:
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _normalize_optional_text(val: Any) -> str | None:
    text = str(val or "").strip()
    if not text:
        return None
    if text in {"-", "--", "—", "暂无", "暂无数据", "无", "N/A", "n/a", "null", "None"}:
        return None
    return text


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
        # mode="json" 将 Decimal 序列化为字符串，保证 raw_output_json 可直接存入 JSON 列，
        # 同时下游 _safe_float / _safe_int / money() 都能接受字符串输入，行为与原实现一致。
        return model.model_dump(by_alias=True, exclude_none=True, mode="json")

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
        pricing_position = _normalize_optional_text(parsed.get("pricingPosition")) or ""
        evidence_summary = _normalize_optional_text(parsed.get("evidenceSummary")) or ""

        risk_notes = _normalize_optional_text(parsed.get("riskNotes"))
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

        sales_weighted_avg = _safe_positive_float(parsed.get("salesWeightedAverage"))
        sales_weighted_median = _safe_positive_float(parsed.get("salesWeightedMedian"))
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

    # ── Task 级 context 拼装 ──────────────────────────────────
    @staticmethod
    def _format_prior_outputs_for_context(
        prior_outputs: dict[int, dict[str, Any]],
        target_order: int,
    ) -> str | None:
        """把已完成 Agent 的 raw_output_json 拼成一段文本，作为下游 Task 的 context。

        行为与原 Crew.kickoff 保持一致：
        - data/market/risk_task（order 1-3）原本 task.context=[]，不依赖其他 Agent → 返回 None
        - manager_task（order=4）原本 task.context=[data,market,risk] → 注入三者 raw_output
          （我们走 task.execute_sync 手工调度，CrewAI 不会自动读取 task.context 列表，必须手动拼接）
        """
        if target_order != 4 or not prior_outputs:
            return None
        sections: list[str] = []
        name_by_order = {
            1: "数据分析Agent",
            2: "市场情报Agent",
            3: "风险控制Agent",
        }
        for order in sorted(prior_outputs.keys()):
            if order >= target_order:
                continue
            name = name_by_order.get(order, f"Agent#{order}")
            payload_text = json.dumps(prior_outputs[order], ensure_ascii=False, default=str)
            sections.append(f"[{name} 的历史输出 JSON]\n{payload_text}")
        return "\n\n".join(sections) if sections else None

    def _write_agent_success_card(
        self,
        *,
        payload: CrewRunPayload,
        order: int,
        parsed: dict[str, Any],
        prior_outputs: dict[int, dict[str, Any]],
    ) -> None:
        """构建并写入单个 Agent 的成功卡片（包含 raw_output 以便后续回放）。"""
        meta = _AGENT_META[order - 1]
        reason_why: str | None = None
        if order == 1:
            thinking, evidence, suggestion = self._build_data_card(payload, parsed)
        elif order == 2:
            thinking, evidence, suggestion = self._build_market_card(parsed)
        elif order == 3:
            thinking, evidence, suggestion = self._build_risk_card(payload, parsed)
        else:
            data_p = prior_outputs.get(1, {})
            market_p = prior_outputs.get(2, {})
            risk_p = prior_outputs.get(3, {})
            thinking, evidence, suggestion, reason_why = self._build_manager_card(
                parsed, data_p, market_p, risk_p
            )

        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=meta["name"],
            display_order=meta["order"],
            thinking_summary=thinking,
            evidence=evidence,
            suggestion=suggestion,
            reason_why=reason_why,
            raw_output=parsed,
        )

    def _write_agent_failed_card(
        self,
        *,
        payload: CrewRunPayload,
        order: int,
        summary: str,
    ) -> None:
        """为失败 Agent 写入 failed 卡片。"""
        meta = _AGENT_META[order - 1]
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

    # ── 主执行方法 ────────────────────────────────────────────
    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        """
        驱动 4 个 Agent 按顺序执行定价决策，支持 Agent 粒度的断点续跑。

        流程：
          1. 构建 LLM → 构建 CrewBundle
          2. ResumeService 计算断点 → 已完成 Agent 的 raw_output 注入下游 context
          3. 对每个需要执行的 Task 调用 task.execute_sync；失败立即写 failed 卡片并抛异常
          4. 所有 Agent 成功后，解析经理决策 → 强制硬约束 → 写入最终结果
        """
        # ── 构建 CrewAI LLM 实例 ──────────────────────────────
        analysis_llm = build_crewai_llm(
            api_key=payload.llm_api_key,
            base_url=payload.llm_base_url,
            model=payload.llm_model,
        )
        manager_llm = build_crewai_llm(
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

        # ── 构建 Crew Bundle ───────────────────────────────────
        logger.info("开始构建定价 Crew (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] building crew task_id={payload.task_id}")
        bundle: CrewBundle = build_pricing_crew(
            payload=payload,
            analysis_llm=analysis_llm,
            manager_llm=manager_llm,
            on_task_done=None,  # 处理已内联到主循环，不再走 callback
        )

        # ── 计算续跑断点 ───────────────────────────────────────
        resume_service = ResumeService(self.db)
        start_from, prior_outputs = resume_service.compute_resume_point(payload.task_id)

        if start_from > 1:
            skipped = sorted(prior_outputs.keys())
            logger.info(
                "任务 %d 部分重试: 从 order=%d 开始，跳过已完成 order=%s",
                payload.task_id,
                start_from,
                skipped,
            )
            debug_log(
                f"[CrewAI] resume_from={start_from} skipped={skipped} task_id={payload.task_id}"
            )
        else:
            debug_log(f"[CrewAI] resume_from=1 (full run) task_id={payload.task_id}")

        # ── 全部 Agent 都已完成的边界情况 ─────────────────────
        if start_from > len(_AGENT_META):
            logger.info(
                "任务 %d 所有 Agent 都已有 completed 记录，直接使用经理输出生成最终结果",
                payload.task_id,
            )
            manager_parsed = prior_outputs.get(4, {})
            return self._finalize_result(payload, manager_parsed)

        # ── 为第一个待执行的 Agent 写 running 占位卡片 ─────────
        first_meta = _AGENT_META[start_from - 1]
        self.log_tool.write_running_card(
            task_id=payload.task_id,
            agent_name=first_meta["name"],
            display_order=first_meta["order"],
        )

        # ── 串行执行剩余 Task ─────────────────────────────────
        for order in range(start_from, len(_AGENT_META) + 1):
            task = bundle.tasks[order - 1]
            agent = bundle.agents_by_order[order]
            meta = _AGENT_META[order - 1]

            # 构造 context：经理 Agent 依赖上游三者的 raw_output；其余 Agent 不注入。
            context_text = self._format_prior_outputs_for_context(
                prior_outputs, target_order=order
            )

            logger.info("Agent [%s] 开始执行 (order=%d)", meta["name"], order)
            debug_log(
                f"[CrewAI] execute_sync agent={meta['code']} order={order} "
                f"prior_orders={sorted(prior_outputs.keys())} task_id={payload.task_id}"
            )

            try:
                task_output = task.execute_sync(
                    agent=agent,
                    context=context_text,
                    tools=agent.tools,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Agent [%s] 执行失败: %s", meta["name"], exc, exc_info=True)
                debug_log(f"[CrewAI] execute_sync failed agent={meta['code']} error={exc}")
                summary = self._summarize_failure_message(exc)
                self._write_agent_failed_card(payload=payload, order=order, summary=summary)
                raise  # 向上抛给 dispatch_service 做 retry_count 递增

            raw = str(task_output.raw) if hasattr(task_output, "raw") else str(task_output)
            debug_log(
                f"[CrewAI] execute_sync done agent={meta['code']} "
                f"raw_len={len(raw)} raw_preview={raw[:200]}"
            )

            parsed = extract_json_object(raw)
            if not parsed:
                exc = AgentOutputValidationError(meta["code"], "输出解析失败")
                logger.warning("Agent [%s] 输出解析失败，写入错误卡片", meta["name"])
                self._write_agent_failed_card(payload=payload, order=order, summary=str(exc))
                raise exc

            try:
                parsed = self._validate_agent_output(meta["code"], parsed)
            except AgentOutputValidationError as exc:
                logger.warning("Agent [%s] 输出结构校验失败: %s", meta["name"], exc, exc_info=True)
                self._write_agent_failed_card(payload=payload, order=order, summary=str(exc))
                raise

            # 成功：把 parsed 存入 prior_outputs 供后续 Agent 使用，同时写 completed 卡片
            prior_outputs[order] = parsed
            logger.info("Agent [%s] 完成，正在写入卡片 (order=%d)", meta["name"], order)
            self._write_agent_success_card(
                payload=payload,
                order=order,
                parsed=parsed,
                prior_outputs=prior_outputs,
            )
            logger.info("Agent [%s] 卡片已写入数据库", meta["name"])

            # 为下一个 Agent 提前写 running 占位
            if order < len(_AGENT_META):
                next_meta = _AGENT_META[order]
                self.log_tool.write_running_card(
                    task_id=payload.task_id,
                    agent_name=next_meta["name"],
                    display_order=next_meta["order"],
                )

        logger.info("Crew 执行完成 (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] crew completed task_id={payload.task_id}")

        manager_parsed = prior_outputs.get(4, {})
        return self._finalize_result(payload, manager_parsed)

    def _finalize_result(
        self,
        payload: CrewRunPayload,
        manager_parsed: dict[str, Any],
    ) -> TaskFinalResult:
        """对经理 Agent 输出做最终校验 + 硬约束，写入 pricing_result 并返回。"""
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
