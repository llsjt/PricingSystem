#!/usr/bin/env python
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from app.schemas.decision import AnalysisRequest

from .orchestrator import pricing_crew_orchestrator


def run_with_request(request: AnalysisRequest):
    """Run the full 4-agent crew workflow from an AnalysisRequest."""
    return asyncio.run(pricing_crew_orchestrator.run_full_workflow(request))


def run_with_payload(payload: Dict[str, Any]):
    """Run the full 4-agent crew workflow from raw payload dict."""
    request = AnalysisRequest.model_validate(payload)
    return run_with_request(request)


def run(payload_json: Optional[str] = None):
    """CLI-friendly entrypoint matching CrewAI project style."""
    if payload_json:
        payload = json.loads(payload_json)
        return run_with_payload(payload)
    raise ValueError("payload_json is required for this project entrypoint")
