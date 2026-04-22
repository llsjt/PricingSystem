# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An e-commerce intelligent pricing platform (graduation project). Three services collaborate: a Vue3 frontend, a Spring Boot Java backend for business logic, and a FastAPI Python backend that orchestrates a multi-agent pricing workflow via CrewAI.

## Architecture

```
Frontend (Vue3, :5173)
  → Java Backend (Spring Boot, :8080)  — business API, task management, result queries
    → Python Backend (FastAPI, :8000)  — agent orchestration, writes results to DB
      → 4 CrewAI Agents: DataAnalysis, MarketIntel, RiskControl, ManagerCoordinator
        → MySQL (pricing_system2.0)
```

- **Java** is the only backend the frontend talks to. It owns product CRUD, Excel import (EasyExcel/淘宝 format), user auth, exposes `/api/**` endpoints, publishes task-dispatch events to RabbitMQ, and streams task progress to the browser over SSE.
- **Python** consumes RabbitMQ dispatch events, runs the 4-agent CrewAI crew, and writes `agent_run_log` / `pricing_result` rows directly to MySQL. Its internal HTTP surface is limited to health, status/detail/logs, and retry-style endpoints for Java-side coordination.
- **Frontend** uses Axios to call Java and receives live task updates from Java SSE endpoints.

## Build & Run Commands

### Java Backend
```bash
cd backend-java
mvn spring-boot:run                    # run (port 8080)
mvn test                               # all tests
mvn test -Dtest=ProductServiceImplTest  # single test class
mvn test -Dtest=ProductServiceImplTest#methodName  # single test method
```
- Java 21, Spring Boot 3.2, MyBatis-Plus 3.5.5, Lombok
- Config: `backend-java/src/main/resources/application.yml`

### Python Backend
```bash
cd backend-python
python -m venv .venv && .venv/Scripts/activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
- Copy `.env.example` to `.env` and fill in `LLM_API_KEY`, `LLM_BASE_URL`, `MODEL`
- Config is loaded via pydantic-settings from `.env` (see `app/core/config.py`)
- On Windows, `python run_server.py` is the fallback when you need the local Selector loop / `h11` settings used by this repo's compatibility wrapper.

### Frontend
```bash
cd frontend
npm install
npm run dev       # dev server (port 5173)
npm run build     # production build (vue-tsc + vite)
```
- Vue 3 + TypeScript + Element Plus + ECharts + Pinia

## Database

MySQL database `pricing_system2.0`. Apply scripts in order:
1. `database/schema.sql` — full schema
2. `database/migration_*.sql` — incremental migrations (apply by date order)

Key domains:
- Product: `product`, `product_sku`, `product_daily_metric`, `traffic_promo_daily`
- Decision: `pricing_task`, `agent_run_log`, `pricing_result`

## Java-Python Integration

The main task-creation path is RabbitMQ-based: Java publishes a dispatch event and the Python worker consumes it asynchronously. Java still calls Python over internal HTTP for readiness checks and task coordination endpoints, and both sides share `INTERNAL_API_TOKEN` for auth. They also share the same MySQL database — Java reads results that Python writes.

## Python Agent Architecture

- `app/agents/` — 4 agent definitions (data_analysis, market_intel, risk_control, manager)
- `app/crew/` — CrewAI crew factory, runtime wrapper, protocol interfaces
- `app/tools/` — agent tools (product data queries, elasticity/profit, risk rules, log/result writers)
- `app/services/competitor_service.py` + `app/services/competitor_providers/` — competitor lookup and enrichment based on the local Tmall CSV index
- `app/api/internal_tasks.py` — internal HTTP routes for task status/detail/logs and retry
- `app/services/rabbitmq_worker_service.py` — consumes RabbitMQ dispatch events and drives worker execution
- `app/services/dispatch_service.py` — prepares task context, normalizes state transitions, and enters orchestration
- `app/services/orchestration_service.py` — runs the CrewAI crew with timeout/budget controls
- CrewAI budget settings (max iterations, session timeout, second-round negotiation) are all configurable via `.env`

## Key Conventions

- Java entities use Lombok `@Data`; mappers extend MyBatis-Plus `BaseMapper`
- Java follows controller → service → mapper layering; VOs for API responses, DTOs for imports
- Python uses SQLAlchemy models in `app/models/`, Pydantic schemas in `app/schemas/`, repository pattern in `app/repos/`
- The market intelligence path uses competitor summaries derived from the local Tmall CSV index (`COMPETITOR_DATA_SOURCE=tmall_csv`); when the index is missing or no rows match, it returns an empty result rather than generating simulated competitors
- All LLM calls go through an OpenAI-compatible endpoint (default: Alibaba DashScope / Qwen)
