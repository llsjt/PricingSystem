# Python 多 Agent 协作后端（最小可运行版）

本目录是毕业设计中的 **Python Agent 协作后端**，负责：
- 接收 Java 后端派发的定价任务
- 组织 4 个 Agent 协作
- 把协作日志写入 `agent_run_log`
- 把最终决策写入 `pricing_result`
- 回写 `pricing_task` 状态与建议价格区间

当前版本已优先满足“可解释、可答辩、可演示”的最小闭环。

## 1. 系统架构

```text
Vue 前端
  -> Java 后端 /api/decision/start
    -> Python 后端 /internal/tasks/dispatch
      -> 4 Agent 协作执行（Data / Market / Risk / Manager）
        -> MySQL: pricing_task / agent_run_log / pricing_result
```

说明：
- Java 负责业务入口与对外 API。
- Python 负责多 Agent 协作，不在 Java 内生成 Agent 结论。
- 前端通过 Java 查询日志与结果（兼容现有页面）。

## 2. 目录结构（核心）

```text
backend-python/
  app/
    api/                 # 内部接口：dispatch/status/retry/health
    core/                # 配置、日志、内部鉴权
    db/                  # SQLAlchemy 会话
    models/              # 数据表映射
    repos/               # 数据访问层（不让 Agent 直接拼 SQL）
    services/            # 调度与编排
    agents/              # 4 个 Agent
    tools/               # 工具层（含可替换的市场数据工具）
    schemas/             # 输入输出结构
    crew/                # 协作装配（保留 CrewAI 兼容入口）
```

## 3. 4 个 Agent 职责

1. 数据分析 Agent（`DATA`）
- 读取商品与日指标，估算销量与利润
- 产出建议价格区间与置信度

2. 市场情报 Agent（`MARKET`）
- 当前使用**模拟竞品数据**（不接真实爬虫）
- 产出市场价带与市场侧建议价

3. 风险控制 Agent（`RISK`）
- 应用利润率、最低价、最高价、折扣等约束
- 给出是否通过、风险等级、是否人工复核

4. 经理协调 Agent（`MANAGER`）
- 汇总三方意见
- 当分歧过大时触发二次协商（非线性）
- 输出最终价格、执行策略、结果摘要

## 4. API 用法（Python 内部接口）

基础前缀：`/internal`

### 4.1 派发任务
- `POST /internal/tasks/dispatch`

请求示例：
```json
{
  "taskId": 101,
  "productId": 31,
  "productIds": [31],
  "strategyGoal": "MAX_PROFIT",
  "constraints": "利润率不低于15%，最低售价不低于99"
}
```

响应示例：
```json
{
  "accepted": true,
  "taskId": 101,
  "status": "RUNNING",
  "message": "accepted"
}
```

### 4.2 查询任务状态
- `GET /internal/tasks/{taskId}/status`

### 4.3 重试任务
- `POST /internal/tasks/{taskId}/retry`

### 4.4 健康检查
- `GET /health`

## 5. 启动步骤

1. 准备数据库（与 Java 共用）
- 使用现有 `pricing_system2.0` 库和表结构。

2. 安装依赖
```bash
cd backend-python
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
```

3. 配置环境变量
- 复制 `.env.example` 为 `.env`
- 重点配置：
  - `MYSQL_*`
  - `INTERNAL_API_TOKEN`（与 Java 约定）

4. 启动服务
```bash
uvicorn app.main:app --reload --port 8000
```

## 6. 市场“爬虫”说明（当前实现）

按当前需求，市场分析暂不接真实爬虫，采用可替换的简化实现：
- `tools/competitor_search_tool.py`
- `tools/competitor_crawler_tool.py`
- `tools/competitor_parse_tool.py`

后续若接入真实爬虫，只需替换这三个工具内部逻辑，`MarketIntelAgent` 与上层编排无需改动。

## 7. 前端展示友好性

为便于前端展示，日志落库包含：
- `agent_code / agent_name / run_order / run_status`
- `output_summary`（中文可读摘要）
- `output_payload`（结构化 JSON）
- `suggested_price / predicted_profit / confidence_score / risk_level`

可直接映射到现有“决策日志”和“结果报告”页面。

