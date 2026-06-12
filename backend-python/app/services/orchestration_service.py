"""
定价决策编排服务（CrewAI 版）
============================
驱动 4 个 CrewAI Agent 执行定价决策，支持分析 Agent 并行执行和 Agent 粒度失败重试。

执行流程：
  1. 构建 LLM 实例
  2. 构建 CrewBundle（4 Agent + 4 Task）
  3. 通过 ResumeService 计算续跑断点（上一轮已完成的 Agent 会被跳过）
  4. 并行执行缺失的三个分析 Agent；已完成 Agent 从 agent_run_log.raw_output_json 复用
  5. 三个分析 Agent 全部结束后统一写入成功 agent_run_log（带 raw_output_json）供下次重试复用
  6. 经理 Agent 完成后 → 解析最终决策 → 强制硬约束校验 → 写入 pricing_result
"""
# 编排服务，负责驱动三个分析智能体并行执行，再由经理智能体完成最终定价决策。


import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agent.definitions import (
    AGENT_KIND_BY_CODE as _AGENT_KIND_BY_CODE,
    AGENT_META as _AGENT_META,
    ANALYSIS_ORDERS as _ANALYSIS_ORDERS,
    MANAGER_ORDER as _MANAGER_ORDER,
    get_agent_meta,
)
from app.agent_outputs.card_mapper import (
    build_data_card,
    build_failed_card,
    build_manager_card,
    build_market_card,
    build_risk_card,
)
from app.agent_outputs.normalizer import (
    AgentOutputValidationError,
    first_present,
    normalize_manager_output_contract,
    normalize_optional_text,
    normalize_selected_agent,
    validate_agent_output,
    validate_without_untrusted_agent_opinion,
)
from app.agent_outputs.parser import parse_and_validate_output
from app.application.cancellation_checker import raise_if_cancelled
from app.crew.crew_factory import CrewBundle, build_pricing_crew
from app.crew.crewai_runtime import build_crewai_llm, debug_log
from app.crew.protocols import CrewRunPayload
from app.domain.final_decision_verifier import FinalDecisionVerifier, VerificationContext, append_guardrail_summary
from app.schemas.agent import AgentOpinionV1
from app.schemas.result import TaskFinalResult
from app.services.resume_fingerprint import attach_resume_meta
from app.services.resume_service import ResumeService
from app.services.progress_event_service import get_progress_event_service
from app.services.runtime_metrics import get_runtime_metrics
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool
from app.repos.task_repo import TaskRepo
from app.utils.math_utils import money
from app.utils.text_utils import MANUAL_REVIEW_STRATEGY, to_risk_level_cn, to_strategy_goal_cn

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


def _safe_non_negative_float(val: Any) -> float | None:
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_float_in_range(val: Any, minimum: float, maximum: float) -> float | None:
    try:
        parsed = float(val)
    except (TypeError, ValueError):
        return None
    if parsed < minimum or parsed > maximum:
        return None
    return parsed


def _safe_positive_float(val: Any) -> float | None:
    return _safe_non_negative_float(val)


def _safe_optional_float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _safe_rate_change(new_value: Any, old_value: Any) -> float | None:
    try:
        new_numeric = float(new_value)
        old_numeric = float(old_value)
    except (TypeError, ValueError):
        return None
    if old_numeric <= 0:
        return None
    return round((new_numeric - old_numeric) / old_numeric, 4)


def _safe_money_delta(new_value: Any, old_value: Any) -> float | None:
    try:
        return round(float(new_value) - float(old_value), 2)
    except (TypeError, ValueError):
        return None


def _normalize_optional_text(val: Any) -> str | None:
    return normalize_optional_text(val)


def _first_present(source: dict[str, Any], *keys: str) -> Any:
    return first_present(source, *keys)


def _normalize_optional_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [item for item in value if item is not None]


def _normalize_selected_agent(val: Any) -> str | None:
    return normalize_selected_agent(val)


def _normalize_manager_output_contract(parsed: dict[str, Any]) -> dict[str, Any]:
    return normalize_manager_output_contract(parsed)


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


def _to_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _normalize_optional_text(item)
        if text:
            result.append(text)
    return result


@dataclass(frozen=True)
class AgentRunOutput:
    raw: str
    tool_audit: list[dict[str, Any]]


def _with_tool_audit(raw_output: dict[str, Any], tool_audit: list[dict[str, Any]]) -> dict[str, Any]:
    if not tool_audit:
        return raw_output
    enriched = dict(raw_output)
    enriched["toolAudit"] = list(tool_audit)
    return enriched


def _audit_raw_output(tool_audit: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not tool_audit:
        return None
    return {"toolAudit": list(tool_audit)}


def _strip_tool_audit(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _strip_tool_audit(item) for key, item in value.items() if key != "toolAudit"}
    if isinstance(value, list):
        return [_strip_tool_audit(item) for item in value]
    return value


class OrchestrationService:
    """4-Agent CrewAI 编排服务：通过 LLM 驱动的多Agent协作完成定价决策。"""

    def __init__(self, db: Session, execution_id: str | None = None, progress_service=None):
        self.db = db
        self.execution_id = execution_id
        self.progress_service = progress_service or get_progress_event_service()
        self.task_repo = TaskRepo(db)
        self.log_tool = LogWriterTool(db, execution_id=execution_id)
        self.result_tool = ResultWriterTool(db, execution_id=execution_id)
        self.final_decision_verifier = FinalDecisionVerifier()

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
            get_runtime_metrics().increment("llmTimeoutCount")
            return "LLM 调用超时"

        parse_tokens = ("json", "parse", "decode", "expecting value", "invalid control character")
        if any(token in normalized for token in parse_tokens):
            return "输出解析失败"

        return "CrewAI 任务执行失败"

    @staticmethod
    def _build_failed_card(summary: str) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
        return build_failed_card(summary)

    @staticmethod
    def _validate_agent_output(agent_code: str, parsed: dict[str, Any]) -> dict[str, Any]:
        return validate_agent_output(agent_code, parsed)

    # ── 从 LLM 输出构建数据分析卡片 ──────────────────────────
    @staticmethod
    def _get_agent_meta(order: int) -> dict[str, Any]:
        return get_agent_meta(order)

    @staticmethod
    def _safe_parallel_tools(agent: Any) -> list[Any]:
        tools = list(getattr(agent, "tools", []) or [])
        safe_tools: list[Any] = []
        for tool in tools:
            tool_name = getattr(getattr(tool, "__class__", None), "__name__", "")
            if tool_name in {"LogWriterTool", "ResultWriterTool"}:
                continue
            safe_tools.append(tool)
        return safe_tools

    def _run_task_sync(
        self,
        *,
        payload: CrewRunPayload,
        order: int,
        task: Any,
        agent: Any,
        context_text: str | None,
        tools: list[Any] | None,
        precomputed_competitor_summary: str | None = None,
    ) -> AgentRunOutput:
        raise_if_cancelled()
        meta = self._get_agent_meta(order)
        logger.info("Agent [%s] 开始执行 (order=%d)", meta["name"], order)
        debug_log(
            f"[CrewAI] execute_sync agent={meta['code']} order={order} "
            f"context_injected={bool(context_text)} task_id={payload.task_id}"
        )
        ctx = None
        token = None
        active_context = None
        try:
            from app.tools.tool_context import ToolContext, active_tool_context
        except ImportError:
            ToolContext = None  # type: ignore[assignment]
        else:
            active_context = active_tool_context
            ctx = ToolContext(
                payload=payload,
                task_id=payload.task_id,
                execution_id=self.execution_id,
                agent_code=meta["code"],
                precomputed_competitor_summary=precomputed_competitor_summary if order == 2 else None,
            )
            token = active_context.set(ctx)

        try:
            task_output = task.execute_sync(
                agent=agent,
                context=context_text,
                tools=tools,
            )
        except Exception as exc:  # noqa: BLE001
            if ctx is not None:
                setattr(exc, "tool_audit", list(getattr(ctx, "tool_audit_logs", []) or []))
            raise
        finally:
            if active_context is not None and token is not None:
                active_context.reset(token)
        raw = str(task_output.raw) if hasattr(task_output, "raw") else str(task_output)
        tool_audit = list(getattr(ctx, "tool_audit_logs", []) or []) if ctx is not None else []
        debug_log(
            f"[CrewAI] execute_sync done agent={meta['code']} "
            f"raw_len={len(raw)} raw_preview={raw[:200]}"
        )
        return AgentRunOutput(raw=raw, tool_audit=tool_audit)

    def _parse_and_validate_output(self, *, order: int, raw: str) -> dict[str, Any]:
        return parse_and_validate_output(order=order, raw=raw)

    def _publish_agent_running(self, payload: CrewRunPayload, order: int) -> None:
        meta = self._get_agent_meta(order)
        self.log_tool.write_running_card(
            task_id=payload.task_id,
            agent_name=meta["name"],
            display_order=meta["order"],
        )
        self.progress_service.publish_sync(
            "AGENT_CARD_RUNNING",
            payload.task_id,
            self.execution_id,
            {"agentName": meta["name"]},
        )

    def _publish_agent_completed(self, payload: CrewRunPayload, order: int) -> None:
        meta = self._get_agent_meta(order)
        self.progress_service.publish_sync(
            "AGENT_CARD_COMPLETED",
            payload.task_id,
            self.execution_id,
            {"agentName": meta["name"], "runStatus": "success"},
        )

    def _run_analysis_phase(
        self,
        *,
        payload: CrewRunPayload,
        bundle: CrewBundle,
        prior_outputs: dict[int, dict[str, Any]],
        orders_to_run: list[int],
    ) -> None:
        if not orders_to_run:
            return

        raise_if_cancelled()
        for order in orders_to_run:
            self._publish_agent_running(payload, order)

        future_by_order: dict[Any, int] = {}
        parsed_by_order: dict[int, dict[str, Any]] = {}
        first_error: Exception | None = None
        with ThreadPoolExecutor(max_workers=max(len(orders_to_run), 1)) as executor:
            for order in orders_to_run:
                task = bundle.tasks[order - 1]
                agent = bundle.agents_by_order[order]
                future = executor.submit(
                    self._run_task_sync,
                    payload=payload,
                    order=order,
                    task=task,
                    agent=agent,
                    context_text=None,
                    tools=self._safe_parallel_tools(agent),
                    precomputed_competitor_summary=bundle.precomputed_competitor_summary,
                )
                future_by_order[future] = order

            for future in as_completed(future_by_order):
                order = future_by_order[future]
                meta = self._get_agent_meta(order)
                try:
                    run_output = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Agent [%s] 执行失败: %s", meta["name"], exc, exc_info=True)
                    tool_audit = list(getattr(exc, "tool_audit", []) or [])
                    self._write_agent_failed_card(
                        payload=payload,
                        order=order,
                        summary=self._summarize_failure_message(exc),
                        raw_output=_audit_raw_output(tool_audit),
                    )
                    if first_error is None:
                        first_error = exc
                    continue

                raw = run_output.raw
                tool_audit = run_output.tool_audit
                try:
                    parsed = self._parse_and_validate_output(order=order, raw=raw)
                except AgentOutputValidationError as exc:
                    logger.warning("Agent [%s] 输出结构校验失败: %s", meta["name"], exc, exc_info=True)
                    self._write_agent_failed_card(
                        payload=payload,
                        order=order,
                        summary=str(exc),
                        raw_output=_audit_raw_output(tool_audit),
                    )
                    if first_error is None:
                        first_error = exc
                    continue

                parsed = self._normalize_output_with_agent_opinion(
                    payload=payload,
                    order=order,
                    parsed=parsed,
                    prior_outputs=prior_outputs,
                )
                parsed = _with_tool_audit(parsed, tool_audit)
                parsed_by_order[order] = parsed

        for order in orders_to_run:
            parsed = parsed_by_order.get(order)
            if parsed is None:
                continue
            prior_outputs[order] = parsed
            self._write_agent_success_card(
                payload=payload,
                order=order,
                parsed=parsed,
                prior_outputs=prior_outputs,
            )
            self._publish_agent_completed(payload, order)

        if first_error is not None:
            raise first_error

    @staticmethod
    def _validate_agent_output(agent_code: str, parsed: dict[str, Any]) -> dict[str, Any]:
        return validate_agent_output(agent_code, parsed)

    @staticmethod
    def _validate_without_untrusted_agent_opinion(model_cls: type[Any], parsed: dict[str, Any], exc: Any) -> dict[str, Any] | None:
        return validate_without_untrusted_agent_opinion(model_cls, parsed)

    @staticmethod
    def _build_opinion_id(task_id: int, agent_code: str, run_attempt: int = 0) -> str:
        return f"task:{task_id}:agent:{agent_code}:attempt:{run_attempt}"

    @staticmethod
    def _find_prior_opinion_id(prior_outputs: dict[int, dict[str, Any]], agent_code: str) -> str | None:
        for output in prior_outputs.values():
            if not isinstance(output, dict):
                continue
            opinion = output.get("agentOpinion")
            if not isinstance(opinion, dict):
                continue
            if str(opinion.get("agentCode") or "") != agent_code:
                continue
            opinion_id = opinion.get("opinionId")
            if opinion_id:
                return str(opinion_id)
        return None

    @staticmethod
    def _extract_upstream_agent_code_from_opinion_ref(value: Any) -> str | None:
        text = str(value or "").strip()
        for agent_code in ("DATA_ANALYSIS", "MARKET_INTEL", "RISK_CONTROL"):
            if text == agent_code or f":agent:{agent_code}:" in text:
                return agent_code
        return None

    @staticmethod
    def _normalize_manager_relation_ids(
        relations: Any,
        prior_outputs: dict[int, dict[str, Any]],
    ) -> Any:
        if not isinstance(relations, dict):
            return relations
        normalized = dict(relations)
        for field_name in (
            "dependsOnOpinionIds",
            "acceptedOpinionIds",
            "rejectedOpinionIds",
            "conflictOpinionIds",
            "selectedOpinionIds",
        ):
            values = normalized.get(field_name)
            if not isinstance(values, list):
                continue
            remapped_values: list[str] = []
            for value in values:
                text = str(value)
                agent_code = OrchestrationService._extract_upstream_agent_code_from_opinion_ref(text)
                prior_opinion_id = (
                    OrchestrationService._find_prior_opinion_id(prior_outputs, agent_code)
                    if agent_code
                    else None
                )
                remapped_values.append(prior_opinion_id or text)
            normalized[field_name] = remapped_values
        return normalized

    @staticmethod
    def _infer_task_id_from_prior_outputs(prior_outputs: dict[int, dict[str, Any]]) -> int:
        for output in prior_outputs.values():
            opinion = output.get("agentOpinion")
            if isinstance(opinion, dict):
                task_id = opinion.get("taskId")
                if isinstance(task_id, int):
                    return task_id
                if isinstance(task_id, str) and task_id.isdigit():
                    return int(task_id)
        return 0

    @staticmethod
    def _infer_run_attempt_from_prior_outputs(prior_outputs: dict[int, dict[str, Any]]) -> int:
        attempts: list[int] = []
        for output in prior_outputs.values():
            opinion = output.get("agentOpinion")
            if not isinstance(opinion, dict):
                continue
            run_attempt = opinion.get("runAttempt")
            if isinstance(run_attempt, int):
                attempts.append(run_attempt)
            elif isinstance(run_attempt, str) and run_attempt.isdigit():
                attempts.append(int(run_attempt))
        return max(attempts, default=0)

    @staticmethod
    def _normalize_agent_opinion(
        *,
        task_id: int,
        run_attempt: int,
        agent_code: str,
        agent_name: str,
        parsed: dict[str, Any],
        prior_outputs: dict[int, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        prior_outputs = prior_outputs or {}
        upstream_opinion_ids = [
            str(opinion_id)
            for order in sorted(prior_outputs.keys())
            if order in {1, 2, 3}
            for opinion_id in [((prior_outputs.get(order) or {}).get("agentOpinion") or {}).get("opinionId")]
            if opinion_id
        ]

        pricing: dict[str, Any] = {
            "recommendedPrice": _first_present(parsed, "suggestedPrice", "finalPrice"),
            "minPrice": parsed.get("suggestedMinPrice"),
            "maxPrice": parsed.get("suggestedMaxPrice"),
            "safeFloorPrice": parsed.get("safeFloorPrice"),
        }
        impact: dict[str, Any] = {
            "expectedSales": parsed.get("expectedSales"),
            "expectedProfit": parsed.get("expectedProfit"),
            "profitGrowth": parsed.get("profitGrowth"),
        }
        market: dict[str, Any] | None = None
        risk: dict[str, Any] | None = None

        if agent_code == "MARKET_INTEL":
            market = {
                "marketFloor": parsed.get("marketFloor"),
                "marketCeiling": parsed.get("marketCeiling"),
                "marketMedian": parsed.get("marketMedian"),
                "marketAverage": parsed.get("marketAverage"),
                "validCompetitorCount": _first_present(parsed, "validCompetitorCount", "usedCompetitorCount"),
                "dataQuality": parsed.get("dataQuality"),
                "sourceStatus": parsed.get("sourceStatus"),
            }
        elif agent_code == "RISK_CONTROL":
            risk = {
                "isPass": parsed.get("isPass"),
                "riskLevel": parsed.get("riskLevel"),
                "needManualReview": parsed.get("needManualReview"),
            }

        relations: dict[str, Any] = {
            "dependsOnOpinionIds": upstream_opinion_ids if agent_code == "MANAGER_COORDINATOR" else [],
            "acceptedOpinionIds": [],
            "rejectedOpinionIds": [],
            "conflictOpinionIds": [],
            "selectedOpinionIds": [],
        }
        decision: dict[str, Any] | None = None
        status = "BLOCKED" if agent_code == "RISK_CONTROL" and not bool(parsed.get("isPass", False)) else "PROPOSED"
        confidence = parsed.get("confidence")

        if agent_code == "MANAGER_COORDINATOR":
            selected_agent = _normalize_selected_agent(_first_present(parsed, "selectedAgent", "selectedOption"))
            selected_opinion_id = (
                OrchestrationService._find_prior_opinion_id(prior_outputs, selected_agent)
                or OrchestrationService._build_opinion_id(task_id, selected_agent, run_attempt)
                if selected_agent
                else None
            )
            decision_type = "MERGE"
            if selected_agent and selected_opinion_id:
                decision_type = "FOLLOW"
                relations["acceptedOpinionIds"] = [selected_opinion_id]
                relations["selectedOpinionIds"] = [selected_opinion_id]
            decision = {
                "decisionType": decision_type,
                "consensusScore": parsed.get("consensusScore"),
                "arbitrationDecision": _first_present(parsed, "arbitrationDecision", "arbitrationSummary", "decisionSummary"),
                "arbitrationReason": _first_present(parsed, "arbitrationReason", "decisionReason"),
            }
            status = "ACCEPTED" if decision_type == "FOLLOW" else "MERGED"
            confidence = confidence if confidence is not None else parsed.get("consensusScore")
        elif agent_code == "RISK_CONTROL":
            confidence = confidence if confidence is not None else 1.0

        base_opinion = {
            "version": "v1",
            "opinionId": OrchestrationService._build_opinion_id(task_id, agent_code, run_attempt),
            "taskId": task_id,
            "runAttempt": run_attempt,
            "agentCode": agent_code,
            "agentName": agent_name,
            "kind": _AGENT_KIND_BY_CODE[agent_code],
            "status": status,
            "summary": str(parsed.get("summary") or parsed.get("resultSummary") or f"{agent_name} opinion"),
            "confidence": confidence,
            "pricing": pricing,
            "impact": impact,
            "market": market,
            "risk": risk,
            "evidence": [
                {
                    "key": "summary",
                    "label": "摘要",
                    "value": parsed.get("summary") or parsed.get("resultSummary") or "",
                    "source": "raw_output_json",
                }
            ],
            "rationale": {
                "thinking": str(parsed.get("thinking") or ""),
                "assumptions": [],
                "notes": [],
            },
            "relations": relations,
            "decision": decision,
        }

        provided_opinion = parsed.get("agentOpinion")
        merged_opinion = (
            _deep_merge_dict(base_opinion, provided_opinion)
            if isinstance(provided_opinion, dict)
            else base_opinion
        )
        if agent_code == "MANAGER_COORDINATOR":
            merged_opinion["relations"] = OrchestrationService._normalize_manager_relation_ids(
                merged_opinion.get("relations"),
                prior_outputs,
            )
        opinion = AgentOpinionV1.model_validate(merged_opinion)
        return opinion.model_dump(by_alias=True, exclude_none=True, mode="json")

    def _normalize_output_with_agent_opinion(
        self,
        *,
        payload: CrewRunPayload,
        order: int,
        parsed: dict[str, Any],
        prior_outputs: dict[int, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        meta = self._get_agent_meta(order)
        normalized = dict(parsed)
        run_attempt = self._resolve_run_attempt(payload.task_id, prior_outputs)
        normalized["agentOpinion"] = self._normalize_agent_opinion(
            task_id=payload.task_id,
            run_attempt=run_attempt,
            agent_code=meta["code"],
            agent_name=meta["name"],
            parsed=normalized,
            prior_outputs=prior_outputs,
        )
        if meta["code"] == "MANAGER_COORDINATOR":
            upstream_opinion_ids = [
                str(opinion_id)
                for upstream_order in (1, 2, 3)
                for opinion_id in [((prior_outputs or {}).get(upstream_order, {}).get("agentOpinion") or {}).get("opinionId")]
                if opinion_id
            ]
            self._validate_manager_relation_ids(normalized["agentOpinion"], upstream_opinion_ids)
        return normalized

    @staticmethod
    def _format_opinions_for_manager_context(
        prior_outputs: dict[int, dict[str, Any]],
        *,
        task_id: int | None = None,
        run_attempt: int | None = None,
    ) -> str | None:
        if not prior_outputs:
            return None
        resolved_task_id = task_id if task_id is not None else OrchestrationService._infer_task_id_from_prior_outputs(prior_outputs)
        resolved_run_attempt = run_attempt if run_attempt is not None else OrchestrationService._infer_run_attempt_from_prior_outputs(prior_outputs)
        opinions: list[dict[str, Any]] = []
        for order in sorted(prior_outputs.keys()):
            if order not in {1, 2, 3}:
                continue
            meta = _AGENT_META[order - 1]
            parsed = prior_outputs[order]
            opinion = parsed.get("agentOpinion")
            if not isinstance(opinion, dict):
                opinion = OrchestrationService._normalize_agent_opinion(
                    task_id=resolved_task_id,
                    run_attempt=resolved_run_attempt,
                    agent_code=meta["code"],
                    agent_name=meta["name"],
                    parsed=parsed,
                    prior_outputs=prior_outputs,
                )
            else:
                opinion = _strip_tool_audit(opinion)
            opinions.append(opinion)
        if not opinions:
            return None
        return "[AgentOpinion 列表]\n" + json.dumps(opinions, ensure_ascii=False, default=str)

    def _resolve_run_attempt(self, task_id: int, prior_outputs: dict[int, dict[str, Any]] | None = None) -> int:
        try:
            task = self.task_repo.get_by_id(task_id)
        except Exception:
            task = None
        if task is not None:
            return max(int(task.retry_count or 0), 0)
        if prior_outputs:
            return self._infer_run_attempt_from_prior_outputs(prior_outputs)
        return 0

    @staticmethod
    def _validate_manager_relation_ids(opinion: dict[str, Any], upstream_opinion_ids: list[str]) -> None:
        if not upstream_opinion_ids:
            return
        relations = opinion.get("relations") if isinstance(opinion.get("relations"), dict) else {}
        depends_on = relations.get("dependsOnOpinionIds") if isinstance(relations.get("dependsOnOpinionIds"), list) else []
        if set(depends_on) != set(upstream_opinion_ids):
            raise AgentOutputValidationError("MANAGER_COORDINATOR", "引用的 dependsOnOpinionIds 与上游 opinionId 不一致")

        for field_name in ("acceptedOpinionIds", "rejectedOpinionIds", "conflictOpinionIds", "selectedOpinionIds"):
            values = relations.get(field_name) if isinstance(relations.get(field_name), list) else []
            invalid_values = [str(value) for value in values if str(value) not in upstream_opinion_ids]
            if invalid_values:
                raise AgentOutputValidationError("MANAGER_COORDINATOR", f"{field_name} 引用了不存在的 opinionId")

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
        price_change_rate = _safe_rate_change(suggested_price, payload.product.current_price)
        profit_growth = _safe_money_delta(expected_profit, payload.baseline_profit)

        suggestion = {
            "priceRange": {"min": min_price, "max": max_price},
            "recommendedPrice": suggested_price,
            "expectedSales": expected_sales,
            "expectedProfit": expected_profit,
            "priceChangeRate": price_change_rate,
            "profitGrowth": profit_growth,
            "expectedProfitRate": round(
                expected_profit / max(suggested_price * max(expected_sales, 1), 0.01), 4
            ),
            "merchantPainPoint": "判断调价后销量和利润是否划算，避免只看价格不看收益",
            "merchantAction": "优先查看利润变化，再结合市场与风控确认是否采用",
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
        if source_status.upper() != "OK":
            merchant_action = "先补充竞品数据或手动复核，不建议按市场价大幅调价"
        elif data_quality.upper() == "LOW" or valid_count < 3:
            merchant_action = "竞品样本偏少，建议小幅试探并保留人工复核"
        else:
            merchant_action = "竞品数据可信，可结合价格带判断是否跟随、卡位或避开低价竞争"

        evidence = [
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

        brand_breakdown = parsed.get("brandBreakdown") or []
        if isinstance(brand_breakdown, list) and brand_breakdown:
            evidence.append({"label": "品牌价格带", "value": brand_breakdown[:5]})

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
            "pricingPosition": None,
            "usedCompetitorCount": valid_count,
            "riskNotes": risk_notes,
            "evidenceSummary": evidence_summary or None,
            "salesWeightedAverage": None,
            "merchantPainPoint": "判断竞品价格能否支撑调价，避免卖贵丢单或卖便宜少赚",
            "merchantAction": merchant_action,
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
            "safeFloorPrice": safe_floor,
            "pass": is_pass,
            "riskLevel": to_risk_level_cn(risk_level),
            "needManualReview": bool(parsed.get("needManualReview", not is_pass)),
            "action": "自动执行" if is_pass else "人工审核",
            "merchantPainPoint": "确认是否会亏损、低毛利或突破商家设置的价格红线",
            "merchantAction": "已满足价格红线，可进入人工审核确认活动节奏" if is_pass else "按安全底价或约束修正后再提交人工审核",
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

        disagreement_points = _normalize_optional_list(
            _first_present(parsed, "disagreementPoints", "conflicts", "disagreements", "conflictPoints")
        )
        accepted_opinions = _normalize_optional_list(parsed.get("acceptedOpinions"))
        rejected_opinions = _normalize_optional_list(parsed.get("rejectedOpinions"))

        suggestion = {
            "finalPrice": _safe_float(parsed.get("finalPrice")),
            "expectedSales": _safe_int(parsed.get("expectedSales")),
            "expectedProfit": _safe_float(parsed.get("expectedProfit")),
            "profitGrowth": _safe_optional_float(parsed.get("profitGrowth")),
            "strategy": MANUAL_REVIEW_STRATEGY,
            "consensusScore": _safe_float_in_range(parsed.get("consensusScore"), 0.0, 1.0),
            "disagreementSummary": _normalize_optional_text(parsed.get("disagreementSummary")),
            "disagreementPoints": disagreement_points,
            "acceptedOpinions": accepted_opinions,
            "rejectedOpinions": rejected_opinions,
            "arbitrationDecision": _normalize_optional_text(
                _first_present(parsed, "arbitrationDecision", "arbitrationSummary", "decisionSummary")
            ),
            "arbitrationReason": _normalize_optional_text(
                _first_present(parsed, "arbitrationReason", "decisionReason")
            ),
            "selectedAgent": _normalize_selected_agent(
                _first_present(parsed, "selectedAgent", "selectedOption")
            ),
            "selectedPrice": _safe_optional_float(parsed.get("selectedPrice")),
            "selectedStrategy": _normalize_optional_text(parsed.get("selectedStrategy")),
            "merchantPainPoint": "给出商家可落地的最终价格、预期收益和复核动作",
            "merchantAction": "进入人工审核，核对库存、活动节奏后再应用建议价",
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
            payload_text = json.dumps(_strip_tool_audit(prior_outputs[order]), ensure_ascii=False, default=str)
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
        normalized_output = parsed if isinstance(parsed.get("agentOpinion"), dict) else self._normalize_output_with_agent_opinion(
            payload=payload,
            order=order,
            parsed=parsed,
            prior_outputs=prior_outputs,
        )
        reason_why: str | None = None
        if order == 1:
            thinking, evidence, suggestion = build_data_card(payload, normalized_output)
        elif order == 2:
            thinking, evidence, suggestion = build_market_card(normalized_output)
        elif order == 3:
            thinking, evidence, suggestion = build_risk_card(payload, normalized_output)
        else:
            data_p = prior_outputs.get(1, {})
            market_p = prior_outputs.get(2, {})
            risk_p = prior_outputs.get(3, {})
            thinking, evidence, suggestion, reason_why = build_manager_card(
                normalized_output, data_p, market_p, risk_p
            )

        self.log_tool.write_agent_card(
            task_id=payload.task_id,
            agent_name=meta["name"],
            display_order=meta["order"],
            thinking_summary=thinking,
            evidence=evidence,
            suggestion=suggestion,
            reason_why=reason_why,
            raw_output=attach_resume_meta(normalized_output, payload),
        )

    def _write_agent_failed_card(
        self,
        *,
        payload: CrewRunPayload,
        order: int,
        summary: str,
        raw_output: dict[str, Any] | None = None,
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
            raw_output=raw_output,
        )
        self.progress_service.publish_sync(
            "AGENT_CARD_COMPLETED",
            payload.task_id,
            self.execution_id,
            {"agentName": meta["name"], "runStatus": "failed"},
        )

    # ── 主执行方法 ────────────────────────────────────────────
    def run(self, payload: CrewRunPayload) -> TaskFinalResult:
        raise_if_cancelled()
        resume_plan = ResumeService(self.db).compute_resume_plan(payload.task_id, payload=payload)
        prior_outputs = dict(resume_plan.prior_outputs)

        if resume_plan.all_done:
            logger.info("Task %d has complete agent outputs; replaying result", payload.task_id)
            return self._finalize_result(payload, prior_outputs.get(_MANAGER_ORDER, {}))

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

        logger.info("开始构建定价 Crew (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] building crew task_id={payload.task_id}")
        bundle: CrewBundle = build_pricing_crew(
            payload=payload,
            analysis_llm=analysis_llm,
            manager_llm=manager_llm,
            on_task_done=None,
            include_competitor_summary=2 in resume_plan.analysis_orders_to_run,
        )

        resume_plan = ResumeService(self.db).compute_resume_plan(payload.task_id, payload=payload)
        prior_outputs = dict(resume_plan.prior_outputs)

        if resume_plan.all_done:
            logger.info("任务 %d 已具备完整 Agent 输出，直接回放经理结果", payload.task_id)
            return self._finalize_result(payload, prior_outputs.get(_MANAGER_ORDER, {}))

        analysis_orders_to_run = resume_plan.analysis_orders_to_run
        if analysis_orders_to_run:
            debug_log(
                f"[CrewAI] parallel_analysis orders={analysis_orders_to_run} "
                f"reused={sorted(prior_outputs.keys())} task_id={payload.task_id}"
            )
            self._run_analysis_phase(
                payload=payload,
                bundle=bundle,
                prior_outputs=prior_outputs,
                orders_to_run=analysis_orders_to_run,
            )
        else:
            debug_log(
                f"[CrewAI] analysis_reused orders={sorted(prior_outputs.keys())} task_id={payload.task_id}"
            )

        if not resume_plan.manager_completed:
            manager_order = _MANAGER_ORDER
            meta = self._get_agent_meta(manager_order)
            raise_if_cancelled()
            self._publish_agent_running(payload, manager_order)
            manager_context = self._format_opinions_for_manager_context(
                prior_outputs,
                task_id=payload.task_id,
                run_attempt=self._resolve_run_attempt(payload.task_id, prior_outputs),
            )
            try:
                run_output = self._run_task_sync(
                    payload=payload,
                    order=manager_order,
                    task=bundle.tasks[manager_order - 1],
                    agent=bundle.agents_by_order[manager_order],
                    context_text=manager_context,
                    tools=list(getattr(bundle.agents_by_order[manager_order], "tools", []) or []),
                    precomputed_competitor_summary=bundle.precomputed_competitor_summary,
                )
                raw = run_output.raw
                tool_audit = run_output.tool_audit
                parsed = self._parse_and_validate_output(order=manager_order, raw=raw)
            except AgentOutputValidationError as exc:
                logger.warning("Agent [%s] 输出结构校验失败: %s", meta["name"], exc, exc_info=True)
                self._write_agent_failed_card(
                    payload=payload,
                    order=manager_order,
                    summary=str(exc),
                    raw_output=_audit_raw_output(locals().get("tool_audit", [])),
                )
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("Agent [%s] 执行失败: %s", meta["name"], exc, exc_info=True)
                self._write_agent_failed_card(
                    payload=payload,
                    order=manager_order,
                    summary=self._summarize_failure_message(exc),
                    raw_output=_audit_raw_output(list(getattr(exc, "tool_audit", []) or [])),
                )
                raise

            parsed = self._normalize_output_with_agent_opinion(
                payload=payload,
                order=manager_order,
                parsed=parsed,
                prior_outputs=prior_outputs,
            )
            parsed = _with_tool_audit(parsed, tool_audit)
            prior_outputs[manager_order] = parsed
            self._write_agent_success_card(
                payload=payload,
                order=manager_order,
                parsed=parsed,
                prior_outputs=prior_outputs,
            )
            self._publish_agent_completed(payload, manager_order)

        logger.info("Crew 执行完成 (task_id=%d)", payload.task_id)
        debug_log(f"[CrewAI] crew completed task_id={payload.task_id}")
        return self._finalize_result(payload, prior_outputs.get(_MANAGER_ORDER, {}), prior_outputs=prior_outputs)

    def _finalize_result(
        self,
        payload: CrewRunPayload,
        manager_parsed: dict[str, Any],
        prior_outputs: dict[int, dict[str, Any]] | None = None,
    ) -> TaskFinalResult:
        """对经理 Agent 输出做最终校验 + 硬约束，写入 pricing_result 并返回。"""
        manager_parsed = _normalize_manager_output_contract(manager_parsed)
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

        verifier = getattr(self, "final_decision_verifier", None) or FinalDecisionVerifier()
        verification = verifier.verify(
            VerificationContext(
                payload=payload,
                final_price=final_price,
                expected_profit=expected_profit,
                prior_outputs=prior_outputs or {},
            )
        )
        if not verification.is_pass:
            logger.warning(
                "硬约束: 最终定价触发风控兜底, task_id=%s, reason_codes=%s",
                payload.task_id,
                verification.reason_codes,
            )
            is_pass = False
            result_summary = append_guardrail_summary(result_summary, verification)
        execute_strategy = verification.execute_strategy

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
        if hasattr(self.result_tool, "set_verification_result"):
            self.result_tool.set_verification_result(verification)
        self.result_tool.write_final_result(final_payload)
        self.progress_service.publish_sync(
            "TASK_MANUAL_REVIEW" if execute_strategy == MANUAL_REVIEW_STRATEGY else "TASK_COMPLETED",
            payload.task_id,
            self.execution_id,
            {
                "finalPrice": str(final_price),
                "expectedSales": expected_sales,
                "expectedProfit": str(expected_profit),
            },
        )
        logger.info(
            "定价结果已写入: task_id=%d, final_price=%s, strategy=%s",
            payload.task_id,
            final_price,
            execute_strategy,
        )

        return final_payload
