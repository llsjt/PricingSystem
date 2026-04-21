# 隐私与数据保留策略

## 适用范围

本策略适用于本仓库中的公测环境和本地演示环境，覆盖以下数据：

- 登录审计日志 `login_audit_log`
- 刷新令牌会话 `auth_refresh_session`
- 定价任务 `pricing_task`
- Agent 过程日志 `agent_run_log`
- 定价结果 `pricing_result`

## 数据分类

- 账户与身份数据：用户名、账号、邮箱、角色、登录来源 IP、User-Agent
- 业务数据：商品、店铺、任务参数、定价建议、执行状态
- 过程数据：Agent 分析摘要、证据、建议、失败原因、traceId

## 保留周期

- 登录审计日志：默认保留 180 天
- 刷新令牌会话：默认保留 30 天，且过期会话优先清理
- 已终态任务及其过程日志、结果：默认保留 365 天
- 运行中任务：不参与自动删除

## 最小化原则

- 公测环境仅保留完成排障和审计所需字段
- 不在前端持久化 refresh token
- Python 仅暴露内部接口，不直接对浏览器开放实时入口

## 清理方式

预览待清理数量：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-retention-policy.ps1
```

实际执行清理：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/apply-retention-policy.ps1 -Apply
```

## 运维要求

1. 正式清理前必须先做数据库备份
2. 不允许在未备份的情况下直接执行 `-Apply`
3. 清理后应复核 `/api/health/metrics` 和 `/health/metrics`
4. 如需延长或缩短保留周期，应在变更记录中说明原因
