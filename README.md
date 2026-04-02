# 智能定价平台（毕业设计）

本项目是一个“前端 + Java 业务后端 + Python 多 Agent 协作后端”的电商定价系统。

## 1. 项目结构

```text
graduation_project/
  frontend/         # Vue3 + Element Plus 前端
  backend-java/     # Spring Boot 业务后端（商品、导入、任务查询）
  backend-python/   # FastAPI 多 Agent 协作后端
  database/         # MySQL 建表脚本
```

## 2. 架构说明

```text
前端
  -> Java /api/decision/start
    -> Python /internal/tasks/dispatch
      -> 4 Agent 协作
        -> MySQL(pricing_task / agent_run_log / pricing_result)
```

职责边界：
- Java：对外 API、任务入口、结果查询、应用建议价。
- Python：执行 Agent 协作并落日志和结果。
- 前端：展示任务状态、协作日志、结果报告。

## 3. 4 Agent 职责

1. 数据分析 Agent
- 分析商品与日指标数据
- 给出销量/利润测算与建议价区间

2. 市场情报 Agent
- 当前使用模拟竞品数据（可替换工具层）
- 给出市场价带与市场侧建议价

3. 风险控制 Agent
- 执行利润率、最低价、最高价、折扣等约束
- 输出风控结论与审核建议

4. 经理协调 Agent
- 统筹三方意见
- 在冲突较大时触发二次协商
- 输出最终价格、执行策略、结果摘要

## 4. 数据库

先执行：
- `database/schema.sql`
- 若需要迁移字段：`database/migration_20260327_external_product.sql`

关键表：
- 商品域：`product` `product_sku` `product_daily_metric` `traffic_promo_daily`
- 决策域：`pricing_task` `agent_run_log` `pricing_result`

## 5. 启动步骤

### 5.1 启动 Java 后端
```bash
cd backend-java
mvn spring-boot:run
```

默认端口：`8080`

### 5.2 启动 Python Agent 后端
```bash
cd backend-python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

默认内部接口前缀：`/internal`

### 5.3 启动前端
```bash
cd frontend
npm install
npm run dev
```

默认端口：`5173`

## 6. Java 与 Python 对接配置

`backend-java/src/main/resources/application.yml`：

```yaml
agent:
  python:
    base-url: http://localhost:8000
    dispatch-path: /internal/tasks/dispatch
    internal-token: ''
```

Python 端 `.env`：
- `INTERNAL_API_TOKEN` 与 Java `internal-token` 保持一致。

## 7. 对外 API（前端仍通过 Java）

- `POST /api/decision/start`：发起任务（Java）
- `GET /api/decision/logs/{taskId}`：查看协作日志（Java 查询数据库）
- `GET /api/decision/result/{taskId}`：查看最终结果（Java 查询数据库）
- `POST /api/decision/apply/{resultId}`：应用建议价（Java）

## 8. Python 内部 API

- `POST /internal/tasks/dispatch`：受理任务并后台执行
- `GET /internal/tasks/{taskId}/status`：查询执行状态
- `POST /internal/tasks/{taskId}/retry`：重试任务
- `GET /health`：健康检查

## 9. 演示建议流程

1. 先导入商品与指标数据。
2. 在“智能定价”发起任务。
3. 在“决策档案”查看日志与结果。
4. 点击“应用建议”回写商品价格。

## 10. 说明

- 当前市场分析工具采用“可替换的模拟实现”，未接入真实爬虫。
- 工具层接口已独立，后续可无缝替换为真实采集逻辑。

