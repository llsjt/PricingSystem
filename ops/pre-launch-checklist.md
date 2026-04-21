# 上线前检查清单

## 一键执行
在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-prelaunch-checks.ps1 -EnvFile .\.env.public-beta
```

如果你只想先跑代码和脚本校验，跳过 `docker compose config`：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-prelaunch-checks.ps1 -EnvFile .\.env.public-beta -SkipComposeValidation
```

## 自动检查顺序
脚本会按下面顺序串行执行，任一步失败都会立即停止：

1. 校验 `.env.public-beta` 是否存在，且关键变量不是空值或占位值
2. 校验 `docker-compose.public-beta.yml` 能否用当前环境文件成功展开
3. 校验 `scripts/` 下全部 PowerShell 脚本语法
4. 校验 Python 运维脚本语法
5. 运行 `backend-java` 的 `mvn -q test`
6. 运行 `backend-python` 的 `pytest`
7. 运行 `backend-python` 的 `compileall`
8. 运行 `frontend` 的 `npm run build`

## 成功标准
脚本最后输出：

```text
所有上线前自动检查已通过。
```

只要没有看到这行，就不要继续上线。

## 上线前人工确认
自动检查通过后，再按下面顺序做人工确认：

1. 确认 `.env.public-beta` 使用的是正式密钥，不含 `change-me`、`example`、`replace` 之类占位值
2. 执行数据库备份：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\db-backup.ps1 -EnvFile .\.env.public-beta
```

3. 部署公测环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\deploy-public-beta.ps1 -EnvFile .\.env.public-beta
```

4. 做一次告警阈值检查：

```powershell
python .\scripts\check-operational-alerts.py --base-url http://127.0.0.1:8080
```

5. 按 [public-beta-runbook.md](/D:/代码/备份/graduation_project/ops/public-beta-runbook.md) 完成最少一次任务创建、取消、结果查看、人工审核和价格应用走查
