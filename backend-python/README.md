# backend-python

Python 后端已经按职责拆成四层，业务代码、CrewAI 编排、FastAPI 服务和运行产物不再混在同一层目录。

## 目录分组

- `src/pricing_crew/core`
  纯业务代码。负责四个 Agent 的定价逻辑、约束判断和通用数据模型。
- `src/pricing_crew/crews`
  CrewAI 编排层。负责 Agent、Task、顺序流程和单次脚本入口。
- `src/pricing_crew/api`
  FastAPI 服务层。负责 HTTP 接口、WebSocket 推送、任务流转和结果落库。
- `src/pricing_crew/infrastructure`
  基础设施层。负责运行配置、数据库连接和 CrewAI 工具。
- `runtime`
  运行产物目录。放本地数据库、日志等非源码文件。
- `tests`
  测试代码目录。测试文件不进入 `src`。

## 启动方式

安装依赖后，可以按服务模式或单次执行模式启动：

```bash
pip install -r requirements.txt
start_server.bat
```

等价命令：

```bash
set PYTHONPATH=%cd%\src
python -m pricing_crew.api.server
```

如果只想按 CrewAI 风格执行一次完整流程，可以在代码里调用：

```python
from pricing_crew.crews.main import run

run(payload_json="...")
```

## 健康检查

- `GET http://127.0.0.1:8000/`
- `GET http://127.0.0.1:8000/api/health`

## Java 对接入口

- `POST http://127.0.0.1:8000/api/decision/start`
