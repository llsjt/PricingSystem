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
- Java 和 Python 健康状态都应为 `ok`

## 调整方式

```powershell
python scripts/check-operational-alerts.py `
  --max-java-queue-depth 80 `
  --max-python-queue-depth 80 `
  --max-stale-running 5
```

## 处置建议

1. 如果 `queueDepth` 持续上升，先检查 Python worker 并发和数据库状态
2. 如果 `staleRunningTasks` 上升，先检查 LLM 超时、Python worker 和 MySQL
3. 如果 `manualReview` backlog 上升，说明自动执行护栏过于保守或输入数据质量下降
4. 如果 `failed` 上升，优先查看 Java traceId 和 Python traceId 对应日志
