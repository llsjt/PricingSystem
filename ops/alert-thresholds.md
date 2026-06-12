# 公测告警阈值

## 检查脚本

```powershell
python scripts/check-operational-alerts.py
```

## 默认阈值

- Java `queueDepth` 不高于 50
- Python `queueDepth` 不高于 50
- `staleRunningTasks` 不高于 3
- `manualReview` backlog 不高于 20
- `failed` 不高于 20
- Python `consumerRetryCount` 不高于 10
- Java `/api/health/ready` 应为 `ok`
- Python Worker 在 Java/Python health payload 中应为 `ok`；若仅 Python Worker 为 `down`，按 Worker 告警处理，不视为 Java 网关不可用
- `activeExecutions` 不应长时间为高值且无下降趋势
- `retryPublishFailureCount`、`casConflictCount`、`progressPublishFailureCount`、`manualReviewWithoutResultCount` 有增长时必须进入人工排查
- `llmTimeoutCount` 默认不高于 5；若持续增长，先降低 worker 并发并检查 LLM 网关超时
- `sseTerminalLatencyMs` 当前仅预留指标名；精确判断需要终态事件采集到 DB 写入和 SSE 发送时间戳后启用阈值

## 调整方式

```powershell
python scripts/check-operational-alerts.py `
  --max-java-queue-depth 80 `
  --max-python-queue-depth 80 `
  --max-stale-running 5 `
  --max-llm-timeouts 10
```

## 处置建议

1. 如果 `queueDepth` 持续上升，先检查 Python worker 并发、RabbitMQ 和数据库状态
2. 如果 `staleRunningTasks` 上升，先检查 LLM 超时、Python worker、心跳和 MySQL
3. 如果 `manualReview` backlog 上升，优先查看 verifier reason codes、输入数据质量和风控约束
4. 如果 `failed` 上升，优先查看 Java traceId 和 Python traceId 对应日志
5. 如果 `retryPublishFailureCount` 上升，先暂停重试入口并恢复 RabbitMQ 发布能力
6. 如果 `casConflictCount` 上升，检查是否存在重复消费、异常 redelivery 或 cancel/finalize 并发
7. 如果 `consumerRetryCount` 上升，检查 RabbitMQ redelivery、worker 重启和 stale lease 配置
8. 如果 `manualReviewWithoutResultCount` 上升，立即检查 Python finalization CAS 与 Java SSE 结果读取链路
