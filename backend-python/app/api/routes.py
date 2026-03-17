from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
from pydantic import BaseModel
from app.schemas.decision import (
    AnalysisRequest, 
    DecisionResponse,
    HealthResponse,
    DataAnalysisResult,
    MarketIntelResult,
    RiskControlResult,
    FinalDecision
)
from app.services.decision_service import decision_service
from app.services.workflow_service import workflow_service
from app.core.ws_manager import manager
import uuid
import logging

# 配置简单日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# --- 请求模型 ---
class DecisionTaskRequest(BaseModel):
    task_id: int
    product_ids: List[int]
    strategy_goal: str
    constraints: str

# --- HTTP Endpoints ---

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    健康检查接口
    """
    return HealthResponse(
        status="healthy", 
        service="agent-backend", 
        version="1.0.0"
    )

# 兼容旧版本的健康检查路径
@router.get("/api/health", response_model=HealthResponse)
async def health_check_api():
    """
    健康检查接口（兼容 /api/health 路径）
    """
    return await health_check()

@router.post("/api/decision/start")
async def start_decision_task(request: DecisionTaskRequest, background_tasks: BackgroundTasks):
    """
    启动决策任务 (由 Java 后端调用)
    """
    try:
        # 在后台执行耗时任务
        background_tasks.add_task(
            workflow_service.execute_task,
            request.task_id,
            request.product_ids,
            request.strategy_goal,
            request.constraints
        )
        return {"status": "started", "task_id": request.task_id}
    except Exception as e:
        logger.error(f"Failed to start task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- WebSocket Endpoints ---

@router.websocket("/ws/decision/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    """
    WebSocket 连接 (由前端调用)
    用于实时推送 Agent 思考过程和决策结果
    """
    await manager.connect(websocket, task_id)
    try:
        while True:
            # 保持连接活跃，接收前端消息 (如 ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, task_id)

# --- Original Agent Endpoints (kept for direct testing) ---

@router.post("/agents/data-analysis", response_model=DataAnalysisResult)
async def analyze_data(request: AnalysisRequest):
    try:
        logger.info(f"Start DataAnalysis for product: {request.product.product_id}")
        result = await decision_service.run_data_analysis(request)
        workflow_service.compose_data_agent_output(request, result)
        return result
    except Exception as e:
        logger.error(f"DataAnalysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Data Analysis Agent Error: {str(e)}")

@router.post("/agents/market-intel", response_model=MarketIntelResult)
async def analyze_market(request: AnalysisRequest):
    try:
        logger.info(f"Start MarketIntel for product: {request.product.product_id}")
        result = await decision_service.run_market_intel(request)
        workflow_service.compose_market_agent_output(request, result)
        return result
    except Exception as e:
        logger.error(f"MarketIntel failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Market Intel Agent Error: {str(e)}")

@router.post("/agents/risk-control", response_model=RiskControlResult)
async def control_risk(request: AnalysisRequest):
    try:
        logger.info(f"Start RiskControl for product: {request.product.product_id}")
        result = await decision_service.run_risk_control(request)
        workflow_service.compose_risk_agent_output(request, result)
        return result
    except Exception as e:
        logger.error(f"RiskControl failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk Control Agent Error: {str(e)}")

@router.post("/agents/manager-decision", response_model=DecisionResponse)
async def make_decision(request: AnalysisRequest):
    task_id = str(uuid.uuid4())
    try:
        logger.info(f"Start Full Decision Task {task_id} for product: {request.product.product_id}")
        final_decision = await decision_service.run_manager_decision(request)
        return DecisionResponse(
            task_id=task_id,
            status="success",
            result=final_decision,
            message="Decision process completed successfully."
        )
    except Exception as e:
        logger.error(f"ManagerDecision failed: {str(e)}")
        return DecisionResponse(
            task_id=task_id,
            status="failed",
            result=None,
            message=f"System Error: {str(e)}"
        )
