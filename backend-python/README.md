# 基于 Multi-Agent 的智能电商决策支持系统

## 1. 项目简介
本项目是一个基于 Multi-Agent 架构的智能电商价格决策支持系统，旨在通过 AI 技术辅助商家进行科学的定价决策。系统利用 CrewAI 和 LangChain 框架，协调多个专业 AI Agent 对商品数据、市场情报和经营风险进行综合分析，最终输出结构化的决策报告。

本系统不仅是一个聊天机器人，更是一个面向真实业务场景的决策引擎，支持销量趋势分析、库存健康度评估、竞品价格监测以及利润风险控制。

## 2. 技术栈
- **语言**: Python 3.10+
- **Web 框架**: FastAPI
- **Agent 框架**: CrewAI (多 Agent 协作编排)
- **LLM 工具链**: LangChain (Prompt 管理与工具封装)
- **大模型**: OpenAI GPT-3.5/4 (或兼容 API，如阿里云 Qwen)
- **数据验证**: Pydantic
- **中间件**: 
  - Redis (预留：任务状态与结果缓存)
  - Chroma (预留：评论与报告向量检索)

## 3. 核心 Agent 设计
系统包含 4 个核心 Agent，采用星型协作模式：

### 3.1 DataAnalysisAgent (数据分析师)
- **职责**: 专注于内部经营数据分析。
- **能力**: 
  - 计算销量趋势（上升/平稳/下降）。
  - 评估库存健康度（积压/正常/紧缺）。
  - 基于库存周转率提出初步折扣建议。

### 3.2 MarketIntelAgent (市场情报官)
- **职责**: 专注于外部市场环境监测。
- **能力**: 
  - 分析竞品价格定位（高端/中端/性价比）。
  - 判断市场竞争强度。
  - 分析用户评论舆情情感。

### 3.3 RiskControlAgent (风控总监)
- **职责**: 财务底线守护者（拥有“一票否决权”）。
- **能力**: 
  - 精确计算毛利率。
  - 测算最大安全折扣区间。
  - 综合退款率评估经营风险。

### 3.4 ManagerCoordinatorAgent (决策经理)
- **职责**: 团队协调与最终决策者。
- **能力**: 
  - 汇总各方报告。
  - 解决冲突（如：市场部建议激进促销 vs 风控部禁止亏损）。
  - 生成最终决策报告（Markdown 格式）。

## 4. 目录结构
```
backend-python/
├── app/
│   ├── agents/                  # Agent 核心逻辑
│   │   ├── data_analysis_agent.py
│   │   ├── market_intel_agent.py
│   │   ├── risk_control_agent.py
│   │   └── manager_coordinator_agent.py
│   ├── api/                     # 接口路由
│   │   └── routes.py
│   ├── core/                    # 核心配置
│   │   └── config.py
│   ├── infrastructure/          # 基础设施客户端
│   │   ├── redis_client.py
│   │   └── chroma_client.py
│   ├── orchestration/           # CrewAI 编排示例
│   │   └── crewai_orchestrator.py
│   ├── schemas/                 # Pydantic 数据模型
│   │   └── decision.py
│   ├── services/                # 业务服务层
│   │   └── decision_service.py
│   ├── utils/                   # 工具库
│   │   ├── langchain_helper.py
│   │   └── report_generator.py
│   └── main.py                  # 应用入口
├── requirements.txt             # 依赖清单
└── .env                         # 环境变量
```

## 5. API 接口说明
所有接口均位于 `/api/v1` 路径下：

| 方法 | 路径 | 描述 |
| --- | --- | --- |
| GET | `/api/v1/health` | 健康检查 |
| POST | `/api/v1/agents/manager-decision` | **核心接口**：触发全流程智能决策 |
| POST | `/api/v1/agents/data-analysis` | 单独调用数据分析 Agent |
| POST | `/api/v1/agents/market-intel` | 单独调用市场情报 Agent |
| POST | `/api/v1/agents/risk-control` | 单独调用风控 Agent |

## 6. 项目启动指南

### 6.1 环境准备
1. 安装 Python 3.10 或更高版本。
2. 克隆项目代码。

### 6.2 安装依赖
```bash
cd backend-python
pip install -r requirements.txt
```

### 6.3 配置环境
在 `backend-python` 根目录下创建 `.env` 文件：
```env
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL_NAME=gpt-3.5-turbo
# 可选配置
# REDIS_HOST=localhost
# CHROMA_DB_PATH=./chroma_db
```

### 6.4 启动服务
```bash
uvicorn app.main:app --reload
```

### 6.5 访问文档
启动成功后，访问浏览器：
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## 7. 当前实现范围
- [x] 基于 FastAPI 的完整工程骨架
- [x] Pydantic 强类型数据模型定义
- [x] 4 个核心 Agent 的业务逻辑实现（基于规则+LLM）
- [x] 多 Agent 冲突解决与决策编排逻辑
- [x] 自动生成 Markdown 决策报告
- [x] Redis 和 Chroma 的客户端封装（预留）

## 8. 后续可扩展方向
1. **接入真实 LLM**: 目前 Agent 内部逻辑以规则为主，可平滑接入 LangChain/CrewAI 调用真实大模型，增强非结构化数据处理能力。
2. **持久化存储**: 启用 Redis 缓存热点决策结果，使用 Chroma 存储历史决策以实现 RAG（检索增强生成）。
3. **数据源对接**: 对接淘宝/京东 API 获取实时销量和竞品数据。
4. **前端可视化**: 开发 Vue/React 前端，展示决策仪表盘。
