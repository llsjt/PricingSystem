import sys
import os
import asyncio

# 添加项目根目录到 Python 路径（解决直接运行时的导入问题）
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings

# 初始化 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Based on Multi-Agent System (CrewAI + LangChain) for E-commerce Pricing Decision",
    docs_url="/docs",  # Swagger UI 路径
    redoc_url="/redoc"
)

# 配置 CORS（允许所有来源访问，用于开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
# 注意：不使用 /api/v1 前缀，与 Java 后端调用保持一致
app.include_router(router, tags=["Agents"])

@app.get("/")
async def root():
    """
    根路径欢迎信息
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }

# 启动服务器的主函数
if __name__ == "__main__":
    import uvicorn
    # 使用 uvicorn 启动 FastAPI 应用
    uvicorn.run(
        "app.main:app",  # 应用路径
        host="0.0.0.0",
        port=8000,
        reload=True,  # 开发模式启用热重载
        workers=1
    )
