# Python 多 Agent 协作后端（最小可运行版）

本目录是毕业设计中的 Python 协作后端，负责：
- 接收 Java 派发的定价任务
- 启动 CrewAI 的 4 Agent 协作过程（真实 LLM 调用）
- 将 Agent 关键输出写入 `agent_run_log`
- 生成最终决策并写入 `pricing_result`
- 回写 `pricing_task` 状态和建议价格区间

## 1. 系统架构

```text
Vue 前端
  -> Java 后端 /api/decision/start
    -> Python 后端 /internal/tasks/dispatch
      -> CrewAI 协作 + 本地规则计算
        -> MySQL (pricing_task / agent_run_log / pricing_result)
```

说明：
- Java 负责业务入口、对外 API 和页面查询。
- Python 负责多 Agent 协作与落库。
- 前端继续通过 Java 查询结果与日志。

## 2. 目录结构

```text
backend-python/
  app/
    api/                # 内部接口：dispatch/status/detail/logs/retry/health
    core/               # 配置、日志、安全、uvicorn loop 适配
    db/                 # SQLAlchemy 会话
    models/             # 表映射：pricing_task / agent_run_log / pricing_result 等
    repos/              # 仓储层（数据库读写）
    services/           # 调度与编排服务
    agents/             # 4 个业务 Agent（Data/Market/Risk/Manager）
    crew/               # CrewAI 运行层（OpenAI 兼容 LLM 调用）
    tools/              # 工具层（数据、风控、市场模拟、日志、结果）
    schemas/            # 接口/协作 DTO
    utils/              # 通用工具
  run_server.py         # Windows 推荐启动入口
```

## 3. 四个 Agent 职责

1. `DATA`（数据分析 Agent）
- 汇总商品、日指标、流量数据
- 输出建议价格区间、预估销量、预估利润

2. `MARKET`（市场情报 Agent）
- 使用可替换的模拟竞品工具
- 输出市场价格带和市场侧建议价

3. `RISK`（风险控制 Agent）
- 校验最低利润、上下限、折扣等约束
- 输出是否通过、风险等级、是否人工复核

4. `MANAGER`（经理协调 Agent）
- 汇总三方意见并给出最终价格
- 输出执行策略与结果摘要

## 4. 多 Agent 特征（非普通顺序流）

- 先启动 CrewAI 的 4 Agent 协作会话（`Process.hierarchical`）。
- 再执行本地业务 Agent 的可解释规则计算并落库。
- 当 `DATA` 与 `MARKET` 价格分歧超过阈值时，触发“二次协商复议”分支，不是单向直线流程。

## 5. API 设计（Python 内部）

基础前缀：`/internal`

### 5.1 派发任务
- `POST /internal/tasks/dispatch`

请求示例：
```json
{
  "taskId": 101,
  "productId": 31,
  "productIds": [31],
  "strategyGoal": "MAX_PROFIT",
  "constraints": "利润率不低于10%"
}
```

### 5.2 查询状态
- `GET /internal/tasks/{taskId}/status`

### 5.3 查询任务详情
- `GET /internal/tasks/{taskId}/detail`

### 5.4 查询 Agent 日志
- `GET /internal/tasks/{taskId}/logs?limit=200`

### 5.5 任务重试
- `POST /internal/tasks/{taskId}/retry`

### 5.6 健康检查
- `GET /health`

## 6. 启动方式

### 6.1 安装依赖
```bash
cd backend-python
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

### 6.2 环境变量
复制 `.env.example` 为 `.env`，至少配置：
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_DB`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `MODEL`
- `INTERNAL_API_TOKEN`（可选，与 Java 对齐）

可选参数：
- `LLM_TIMEOUT_SECONDS`（默认 60 秒）

### 6.3 启动服务（Windows 推荐）
```bash
python run_server.py
```

说明：
- `run_server.py` 使用自定义 Selector loop，规避 Windows + Python 3.13 下 uvicorn 的 Proactor `WinError 10014`。

## 7. 可演示数据闭环

一次成功任务会产生：
- `pricing_task`：`PENDING/RUNNING -> COMPLETED`
- `agent_run_log`：至少 5 条（`CREWAI + DATA + MARKET + RISK + MANAGER`）
- `pricing_result`：最终价格、预估销量、预估利润、执行策略

前端可通过 Java 现有接口查看：
- 任务列表
- 任务对比结果
- Agent 日志
