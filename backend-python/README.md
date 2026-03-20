# backend-python

This backend is rebuilt to follow CrewAI project layout:

- `pyproject.toml`
- `.env`
- `src/pricing_crew/main.py`
- `src/pricing_crew/crew.py`
- `src/pricing_crew/tools/custom_tool.py`
- `src/pricing_crew/config/agents.yaml`
- `src/pricing_crew/config/tasks.yaml`

Additional runtime modules are kept for environment config, database integration, crawler integration, API server, and task workflow.

## Run

```bash
pip install -r requirements.txt
start_server.bat
```

## Health check

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/api/health`

## Java-compatible entrypoint

- `POST http://127.0.0.1:8000/api/decision/start`
