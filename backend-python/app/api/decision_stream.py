import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask

router = APIRouter(tags=["pricing-stream"])

SCHEMA_VERSION = "1.0.0"
CHANNEL = "pricing.task.card"

AGENT_META = {
    1: {"agentCode": "DATA_ANALYSIS", "agentName": "数据分析Agent"},
    2: {"agentCode": "MARKET_INTEL", "agentName": "市场情报Agent"},
    3: {"agentCode": "RISK_CONTROL", "agentName": "风险控制Agent"},
    4: {"agentCode": "MANAGER_COORDINATOR", "agentName": "经理协调Agent"},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_message(task_id: int, message_type: str) -> dict:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "channel": CHANNEL,
        "type": message_type,
        "taskId": task_id,
        "timestamp": _now_iso(),
    }


def _serialize_agent_card(task_id: int, item: AgentRunLog) -> dict:
    order = int(item.display_order or item.speak_order or 0)
    meta = AGENT_META.get(order, {})
    return {
        **_base_message(task_id, "agent_card"),
        "agentCode": meta.get("agentCode") or f"AGENT_{order}",
        "agentName": item.role_name or meta.get("agentName") or f"Agent-{order}",
        "displayOrder": order,
        "stage": "completed",
        "card": {
            "thinking": item.thinking_summary or item.thought_content or "",
            "evidence": item.evidence_json if isinstance(item.evidence_json, list) else [],
            "suggestion": item.suggestion_json if isinstance(item.suggestion_json, dict) else {},
            "reasonWhy": item.final_reason,
        },
    }


async def _stream_task_cards(websocket: WebSocket, task_id: int) -> None:
    await websocket.accept()
    last_log_id = 0
    sent_started = False

    try:
        while True:
            with SessionLocal() as db:
                task = db.get(PricingTask, task_id)
                if task is None:
                    await websocket.send_json(
                        {
                            **_base_message(task_id, "task_failed"),
                            "message": f"task not found: {task_id}",
                        }
                    )
                    break

                if not sent_started:
                    await websocket.send_json(
                        {
                            **_base_message(task_id, "task_started"),
                            "status": task.task_status,
                        }
                    )
                    sent_started = True

                stmt = (
                    select(AgentRunLog)
                    .where(AgentRunLog.task_id == task_id, AgentRunLog.id > last_log_id)
                    .order_by(AgentRunLog.id.asc())
                )
                logs = list(db.scalars(stmt).all())
                for log_item in logs:
                    await websocket.send_json(_serialize_agent_card(task_id, log_item))
                    last_log_id = int(log_item.id)

                result = db.scalar(select(PricingResult).where(PricingResult.task_id == task_id).limit(1))
                if result is not None:
                    await websocket.send_json(
                        {
                            **_base_message(task_id, "task_completed"),
                            "result": {
                                "finalPrice": float(result.final_price),
                                "expectedSales": int(result.expected_sales or 0),
                                "expectedProfit": float(result.expected_profit),
                                "strategy": result.execute_strategy,
                                "summary": result.result_summary,
                            },
                        }
                    )
                    break

                if (task.task_status or "").upper() == "FAILED":
                    await websocket.send_json(
                        {
                            **_base_message(task_id, "task_failed"),
                            "message": "task failed",
                        }
                    )
                    break

            await asyncio.sleep(0.6)
    except WebSocketDisconnect:
        return
    except Exception as exc:  # noqa: BLE001
        try:
            await websocket.send_json(
                {
                    **_base_message(task_id, "task_failed"),
                    "message": str(exc),
                }
            )
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.websocket("/ws/pricing/tasks/{task_id}")
async def stream_pricing_cards(websocket: WebSocket, task_id: int) -> None:
    await _stream_task_cards(websocket, task_id)


# 兼容旧前端路径
@router.websocket("/ws/decision/{task_id}")
async def stream_decision_logs(websocket: WebSocket, task_id: int) -> None:
    await _stream_task_cards(websocket, task_id)
