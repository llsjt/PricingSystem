# 智能定价实验室 - 前后端联调报告

## 1. 接口清单 (Interface List)

### 1.1 Java 后端接口 (Spring Boot :8080)

| 接口名称 | HTTP 方法 | URL | 说明 |
| :--- | :--- | :--- | :--- |
| **启动决策任务** | POST | `/api/decision/start` | 接收前端选中的商品ID和策略配置，创建任务并调用 Python Agent |
| **获取任务结果** | GET | `/api/decision/result/{taskId}` | 获取任务生成的最终定价建议列表 |
| **获取商品列表** | GET | `/api/product/list` | 分页查询商品列表 (用于任务配置选择) |

### 1.2 Python Agent 接口 (FastAPI :8000)

| 接口名称 | HTTP 方法 | URL | 说明 |
| :--- | :--- | :--- | :--- |
| **执行决策工作流** | POST | `/api/decision/start` | 接收任务ID和商品ID，异步启动多智能体协作流程 |
| **实时思考流** | WS | `/ws/decision/{taskId}` | WebSocket 连接，实时推送 Agent 思考过程和中间结果 |
| **数据分析 Agent** | POST | `/agents/data-analysis` | 独立调用数据分析能力 |
| **市场情报 Agent** | POST | `/agents/market-intel` | 独立调用市场情报分析能力 |
| **风控 Agent** | POST | `/agents/risk-control` | 独立调用风控能力 |

## 2. 数据流转与协议 (Data Flow & Protocol)

### 2.1 启动任务流程
1. **Frontend -> Java**: `POST /api/decision/start`
   ```json
   {
     "productIds": [1001, 1002],
     "strategyGoal": "MAX_PROFIT",
     "constraints": "利润率 > 15%"
   }
   ```
2. **Java -> DB**: 创建 `DecTask` 记录 (Status: PENDING)
3. **Java -> Python**: `POST http://localhost:8000/api/decision/start`
   ```json
   {
     "task_id": 12345,
     "product_ids": [1001, 1002],
     "strategy_goal": "MAX_PROFIT",
     "constraints": "利润率 > 15%"
   }
   ```
4. **Python**: 启动后台任务，返回 `{"status": "started", "task_id": 12345}`

### 2.2 实时监控流程
1. **Frontend -> Python**: `WS ws://localhost:8000/ws/decision/12345`
2. **Python -> Frontend**: 推送思考过程 (Streaming)
   ```json
   {
     "is_stream": true,
     "is_start": true,
     "agent_role": "数据分析师",
     "step_order": 1,
     "timestamp": "10:00:01"
   }
   ```
   ```json
   {
     "is_stream": true,
     "agent_role": "数据分析师",
     "thought_content": "正在分析近7天销量数据...",
     "timestamp": "10:00:02"
   }
   ```
3. **Python -> DB**: 决策完成后，写入 `dec_result` 表
4. **Python -> Frontend**: 推送最终结果信号
   ```json
   {
     "type": "result",
     "product_id": 1001,
     "data": { ... }
   }
   ```

### 2.3 结果查看流程
1. **Frontend -> Java**: `GET /api/decision/result/12345`
2. **Java -> DB**: 查询 `dec_result` 表
3. **Java -> Frontend**: 返回结果列表
   ```json
   {
     "code": 200,
     "data": [
       {
         "productId": 1001,
         "suggestedPrice": 145.00,
         "profitChange": 0.05,
         "isAccepted": false
       }
     ]
   }
   ```

## 3. 错误码说明 (Error Codes)

| 错误码 | 描述 | 解决方案 |
| :--- | :--- | :--- |
| `500` | System Error | 检查后端日志，确认数据库连接或 Python 服务状态 |
| `404` | Not Found | 检查 URL 拼写或资源是否存在 (如商品ID无效) |
| `400` | Bad Request | 检查请求参数格式 (如 strategyGoal 枚举值错误) |
| `WS_CLOSE` | WebSocket Disconnect | 网络波动或任务超时，建议刷新重试 |

## 4. 联调注意事项
- 确保 MySQL 服务已启动且 `schema.sql` 已执行。
- 确保 Redis 服务已启动 (Agent 缓存依赖)。
- 确保 Python 环境已安装 `requirements.txt` 所有依赖。
- 前端 `PricingLab.vue` 中的 WebSocket URL 需指向 `:8000` (Python)，HTTP API 指向 `:8080` (Java)。
