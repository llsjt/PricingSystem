"""FastAPI 服务模块，提供前后端联调所需接口。"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    FastAPI,
    File,
    HTTPException,
    Query,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from pricing_crew.config.runtime import settings
from pricing_crew.decision_service import decision_service
from pricing_crew.schemas import (
    AnalysisRequest,
    DataAnalysisResult,
    DecisionResponse,
    DecisionTaskRequest,
    FinalDecision,
    HealthResponse,
    MarketIntelResult,
    RiskControlResult,
)
from pricing_crew.workflow import workflow_service
from pricing_crew.ws_manager import manager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def api_ok(data: Any = None, message: str = "success") -> Dict[str, Any]:
    return {"code": 200, "data": data, "message": message}


def _project_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _read_env_map() -> Dict[str, str]:
    path = _project_env_path()
    mapping: Dict[str, str] = {}
    if not path.exists():
        return mapping
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        mapping[key.strip()] = value.strip()
    return mapping


def _update_env_file(values: Dict[str, str]) -> None:
    path = _project_env_path()
    existing_lines: List[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    keys = set(values.keys())
    updated: List[str] = []
    touched: set[str] = set()
    for line in existing_lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                updated.append(f"{key}={values[key]}")
                touched.add(key)
                continue
        updated.append(line)
    for key in keys:
        if key not in touched:
            updated.append(f"{key}={values[key]}")

    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def _mask_key(value: str) -> str:
    text = value.strip()
    if len(text) <= 8:
        return text
    return f"{text[:4]}***{text[-4:]}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    workflow_service.bootstrap()
    yield


router = APIRouter()

DEMO_USERS: Dict[str, Dict[str, Any]] = {
    "admin": {
        "id": 1,
        "username": "admin",
        "password": "123456",
        "email": "admin@example.com",
        "role": "admin",
        "displayName": "系统管理员",
        "createdAt": "2026-01-01 00:00:00",
    },
    "operator": {
        "id": 2,
        "username": "operator",
        "password": "123456",
        "email": "operator@example.com",
        "role": "operator",
        "displayName": "运营专员",
        "createdAt": "2026-01-02 00:00:00",
    },
}


def _next_user_id() -> int:
    return max([int(user.get("id") or 0) for user in DEMO_USERS.values()] + [0]) + 1


def _get_user_by_id(user_id: int) -> Dict[str, Any] | None:
    for user in DEMO_USERS.values():
        if int(user.get("id") or 0) == user_id:
            return user
    return None


def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": int(user["id"]),
        "username": user["username"],
        "email": user.get("email") or "",
        "createdAt": user.get("createdAt") or "",
    }


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", service="pricing-agent-backend", version=settings.app_version)


@router.get("/api/health", response_model=HealthResponse)
async def health_check_api() -> HealthResponse:
    return await health_check()


@router.get("/api/products/list")
async def get_product_list(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    keyword: str = Query(default=""),
    dataSource: str = Query(default=""),
):
    return api_ok(
        workflow_service.get_product_list(
            page=page,
            size=size,
            keyword=keyword,
            data_source=dataSource,
        )
    )


@router.post("/api/products/add")
async def add_product(payload: Dict[str, Any] = Body(...)):
    try:
        return api_ok(workflow_service.add_product_manual(payload), "新增商品成功")
    except Exception as exc:
        logger.exception("新增商品失败")
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/api/products/batch-delete")
async def batch_delete_products(ids: str = Query(default="")):
    try:
        values = [int(item) for item in ids.split(",") if item.strip()]
        deleted = workflow_service.batch_delete_products(values)
        return api_ok({"deleted": deleted}, "批量删除成功")
    except Exception as exc:
        logger.exception("批量删除失败")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/products/template")
async def download_product_template():
    content = workflow_service.build_product_template()
    headers = {"Content-Disposition": "attachment; filename=product_template.xlsx"}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/api/products/import")
async def import_products(file: UploadFile = File(...)):
    try:
        payload = await file.read()
        result = workflow_service.import_products_from_excel(payload, filename=file.filename or "")
        return api_ok(result["message"], "导入成功")
    except Exception as exc:
        logger.exception("导入商品失败")
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/products/{product_id}/trend")
async def get_product_trend(product_id: int, days: int = Query(default=30, ge=7, le=180)):
    try:
        return api_ok(workflow_service.get_product_trend(product_id, days))
    except Exception as exc:
        logger.exception("获取商品趋势失败")
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/api/user/login")
async def login(payload: Dict[str, Any] = Body(...)):
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    user = DEMO_USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return api_ok(
        {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "displayName": user["displayName"],
        },
        "登录成功",
    )


@router.post("/api/user/logout")
async def logout():
    return api_ok(True, "已退出登录")


@router.get("/api/user/list")
async def get_user_list(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
):
    users = sorted((_public_user(user) for user in DEMO_USERS.values()), key=lambda item: item["id"])
    start = (page - 1) * size
    end = start + size
    return api_ok({"records": users[start:end], "total": len(users)})


@router.post("/api/user/add")
async def add_user(payload: Dict[str, Any] = Body(...)):
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()
    email = str(payload.get("email") or "").strip()
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if username in DEMO_USERS:
        raise HTTPException(status_code=400, detail="用户名已存在")

    DEMO_USERS[username] = {
        "id": _next_user_id(),
        "username": username,
        "password": password,
        "email": email,
        "role": "operator",
        "displayName": username,
        "createdAt": "2026-03-19 00:00:00",
    }
    return api_ok(_public_user(DEMO_USERS[username]), "用户创建成功")


@router.put("/api/user/{user_id}")
async def update_user(user_id: int, payload: Dict[str, Any] = Body(...)):
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    username = str(payload.get("username") or user["username"]).strip()
    email = str(payload.get("email") or user.get("email") or "").strip()
    password = str(payload.get("password") or "").strip()

    if username != user["username"] and username in DEMO_USERS:
        raise HTTPException(status_code=400, detail="用户名已存在")

    old_key = user["username"]
    user["username"] = username
    user["email"] = email
    if password:
        user["password"] = password
    if old_key != username:
        DEMO_USERS.pop(old_key, None)
        DEMO_USERS[username] = user
    return api_ok(_public_user(user), "用户更新成功")


@router.delete("/api/user/{user_id}")
async def delete_user(user_id: int):
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user["username"] == "admin":
        raise HTTPException(status_code=400, detail="admin 用户不可删除")
    DEMO_USERS.pop(user["username"], None)
    return api_ok(True, "用户删除成功")


@router.get("/api/config/all")
async def get_all_config():
    env_map = _read_env_map()
    dashscope_api_key = env_map.get("DASHSCOPE_API_KEY") or env_map.get("OPENAI_API_KEY") or settings.openai_api_key
    agent_model = env_map.get("AGENT_MODEL") or env_map.get("OPENAI_MODEL_NAME") or settings.openai_model_name
    return api_ok(
        {
            "DASHSCOPE_API_KEY": dashscope_api_key,
            "AGENT_MODEL": agent_model,
            "maskedApiKey": _mask_key(dashscope_api_key),
        }
    )


@router.post("/api/config/update")
async def update_config(payload: Dict[str, Any] = Body(...)):
    dashscope_api_key = str(payload.get("DASHSCOPE_API_KEY") or "").strip()
    agent_model = str(payload.get("AGENT_MODEL") or "").strip() or settings.openai_model_name
    values = {
        "DASHSCOPE_API_KEY": dashscope_api_key,
        "AGENT_MODEL": agent_model,
        "OPENAI_API_KEY": dashscope_api_key,
        "OPENAI_MODEL_NAME": agent_model,
    }
    _update_env_file(values)
    os.environ["OPENAI_API_KEY"] = dashscope_api_key
    os.environ["OPENAI_MODEL_NAME"] = agent_model
    return api_ok(True, "配置已保存")


@router.post("/api/decision/start")
async def start_decision_task(request: DecisionTaskRequest, background_tasks: BackgroundTasks):
    if not request.product_ids:
        raise HTTPException(status_code=400, detail="至少选择一个商品")
    try:
        # 业务任务在 Spring Boot 侧建单时，会把 task_id 透传到 Python；
        # Python 仅负责 agent 编排和流式输出，不再创建重复任务。
        if request.task_id is not None:
            task_id = int(request.task_id)
            if not workflow_service.task_exists(task_id):
                workflow_service.create_task(
                    product_ids=request.product_ids,
                    strategy_goal=request.strategy_goal,
                    constraints=request.constraints,
                    predefined_task_id=task_id,
                )
        else:
            task_id = workflow_service.create_task(
                product_ids=request.product_ids,
                strategy_goal=request.strategy_goal,
                constraints=request.constraints,
            )
        background_tasks.add_task(
            workflow_service.execute_task,
            task_id,
            request.product_ids,
            request.strategy_goal,
            request.constraints,
        )
        return api_ok(task_id, "任务已启动")
    except Exception as exc:
        logger.exception("启动智能定价任务失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/decision/result/{task_id}")
async def get_task_result(task_id: int):
    return api_ok(workflow_service.get_task_results(task_id))


@router.get("/api/decision/logs/{task_id}")
async def get_task_logs(task_id: int):
    return api_ok(workflow_service.get_task_logs(task_id))


@router.post("/api/decision/apply/{result_id}")
async def apply_decision(result_id: int):
    try:
        return api_ok(workflow_service.apply_result(result_id), "价格建议已应用")
    except Exception as exc:
        logger.exception("应用价格建议失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/decision/tasks")
async def get_decision_tasks(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    status: str = Query(default=""),
    strategyType: str = Query(default=""),
    startTime: str = Query(default=""),
    endTime: str = Query(default=""),
    sortOrder: str = Query(default="desc"),
):
    return api_ok(
        workflow_service.get_task_archive(
            page=page,
            size=size,
            status=status,
            strategy_type=strategyType,
            start_time=startTime,
            end_time=endTime,
            sort_order=sortOrder,
        )
    )


@router.get("/api/decision/tasks/stats")
async def get_decision_task_stats(
    strategyType: str = Query(default=""),
    startTime: str = Query(default=""),
    endTime: str = Query(default=""),
):
    return api_ok(
        workflow_service.get_task_stats(
            strategy_type=strategyType,
            start_time=startTime,
            end_time=endTime,
        )
    )


@router.get("/api/decision/comparison/{task_id}")
async def get_decision_comparison(task_id: int):
    return api_ok(workflow_service.get_task_comparison(task_id))


@router.post("/api/decision/reject/{result_id}")
async def reject_decision(result_id: int, payload: Dict[str, Any] = Body(default={})):
    reason = str(payload.get("reason") or "").strip()
    try:
        return api_ok(workflow_service.reject_result(result_id, reason), "价格建议已驳回")
    except Exception as exc:
        logger.exception("驳回价格建议失败")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/api/decision/export/{task_id}")
async def export_decision_report(task_id: int):
    content = workflow_service.export_task_report_csv(task_id)
    headers = {"Content-Disposition": f"attachment; filename=decision_task_{task_id}.csv"}
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=headers)


@router.websocket("/ws/decision/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str):
    await manager.connect(websocket, task_id)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, task_id)
    except Exception:
        manager.disconnect(websocket, task_id)


@router.post("/agents/data-analysis", response_model=DataAnalysisResult)
async def analyze_data(request: AnalysisRequest):
    return await decision_service.run_data_analysis(request)


@router.post("/agents/market-intel", response_model=MarketIntelResult)
async def analyze_market(request: AnalysisRequest):
    return await decision_service.run_market_intel(request)


@router.post("/agents/risk-control", response_model=RiskControlResult)
async def control_risk(request: AnalysisRequest):
    return await decision_service.run_risk_control(request)


@router.post("/agents/manager-decision", response_model=DecisionResponse)
async def make_decision(request: AnalysisRequest):
    task_id = str(uuid.uuid4())
    try:
        final_decision: FinalDecision = await decision_service.run_manager_decision(request)
        return DecisionResponse(
            task_id=task_id,
            status="success",
            result=final_decision,
            message="四智能体决策流程执行成功。",
        )
    except Exception as exc:
        logger.exception("经理决策接口执行失败")
        return DecisionResponse(
            task_id=task_id,
            status="failed",
            result=None,
            message=f"系统错误：{exc}",
        )


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="CrewAI 风格四智能体智能定价服务",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "message": f"欢迎使用 {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs",
    }


def run_api_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    import uvicorn

    config = uvicorn.Config(app=app, host=host, port=port, reload=reload, workers=1)
    server = uvicorn.Server(config)

    if sys.platform.startswith("win"):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
        return

    server.run()


if __name__ == "__main__":
    run_api_server()
