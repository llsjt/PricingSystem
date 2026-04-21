# 公测压测说明

## 目标

- 验证 50-100 个并发任务创建请求是否能被 Java 接受
- 验证部分任务的 SSE 实时流是否能正常收口到终态
- 输出一份可归档的 JSON 报告，便于记录本次压测结果

## 前置条件

- 本地或测试环境已经启动：
  - Java: `http://127.0.0.1:8080`
  - Python: `http://127.0.0.1:8000`
  - MySQL: `pricing_system2.0`
- 已有一个可用于定价任务的商品 ID
- 已有一个可登录账号

## 示例命令

```powershell
python scripts/load-test-public-beta.py `
  --base-url http://127.0.0.1:8080 `
  --username admin `
  --password Admin123! `
  --product-id 1 `
  --requests 100 `
  --concurrency 50 `
  --sse-watchers 5 `
  --report-file ops/reports/load-test-2026-04-08.json
```

## 输出项

- `successful` / `failed`
- `latency.minMs`
- `latency.avgMs`
- `latency.p95Ms`
- `latency.maxMs`
- `taskIds`
- `sse`
- `results`

## 通过标准

- 任务创建失败率不高于 5%
- SSE 监听到的任务都能收到 `task_completed` 或 `task_failed`
- Java `/api/health/metrics` 中没有明显异常积压
- Python `/health/metrics` 中 `queue.started=true`，且 `staleRunningTasks` 不持续增长

## 压测后检查

1. 查看 [HealthController.java](/D:/代码/备份/graduation_project/backend-java/src/main/java/com/example/pricing/controller/HealthController.java) 的 `/api/health/metrics`
2. 查看 [health.py](/D:/代码/备份/graduation_project/backend-python/app/api/health.py) 的 `/health/metrics`
3. 如需回库清理压测数据，先执行备份，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-retention-policy.ps1
```
