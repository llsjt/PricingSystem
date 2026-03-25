#!/usr/bin/env python
"""命令行入口模块，支持按请求负载运行四智能体流程。"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from pricing_crew.core.schemas import AnalysisRequest
from pricing_crew.crews.orchestrator import pricing_crew_orchestrator


def run_with_request(request: AnalysisRequest):
    return asyncio.run(pricing_crew_orchestrator.run_full_workflow(request))


def run_with_payload(payload: Dict[str, Any]):
    request = AnalysisRequest.model_validate(payload)
    return run_with_request(request)


def run(payload_json: Optional[str] = None):
    if payload_json:
        payload = json.loads(payload_json)
        return run_with_payload(payload)
    raise ValueError("payload_json is required")


if __name__ == "__main__":
    raise SystemExit("Use pricing_crew.crews.main.run(payload_json=...) or API server entrypoint.")
