"""Resume replay fingerprint helpers.

Completed agent outputs are safe to replay only when the prompt contract and
task payload constraints still match the current run. The metadata lives inside
raw_output_json.__meta so this remains a schema-free P1 guardrail.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass, fields
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.crew.protocols import CrewRunPayload
from app.agent_prompts.prompt_versions import PRICING_PROMPT_VERSION

RESUME_META_KEY = "__meta"
RESUME_SCHEMA_VERSION = 1
PROMPT_VERSION = PRICING_PROMPT_VERSION


def payload_hash(payload: CrewRunPayload) -> str:
    canonical = _canonical_payload(payload)
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def build_resume_meta(payload: CrewRunPayload) -> dict[str, Any]:
    return {
        "resume": {
            "schemaVersion": RESUME_SCHEMA_VERSION,
            "promptVersion": PROMPT_VERSION,
            "payloadHash": payload_hash(payload),
        }
    }


def attach_resume_meta(raw: dict[str, Any], payload: CrewRunPayload) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return raw
    enriched = dict(raw)
    existing_meta = enriched.get(RESUME_META_KEY)
    meta = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    meta.update(build_resume_meta(payload))
    enriched[RESUME_META_KEY] = meta
    return enriched


def strip_replay_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in raw.items() if key not in {"toolAudit", RESUME_META_KEY}}


def is_resume_meta_compatible(raw: dict[str, Any], expected_meta: dict[str, Any] | None) -> bool:
    if expected_meta is None:
        return True
    meta = raw.get(RESUME_META_KEY)
    if not isinstance(meta, dict):
        return False
    return meta.get("resume") == expected_meta.get("resume")


def _canonical_payload(payload: CrewRunPayload) -> dict[str, Any]:
    return {
        "strategyGoal": payload.strategy_goal,
        "constraints": _normalize(payload.constraints or {}),
        "product": _normalize(payload.product),
        "metrics": _normalize(payload.metrics or []),
        "traffic": _normalize(payload.traffic or []),
        "baselineSales": int(payload.baseline_sales or 0),
        "baselineProfit": _normalize(payload.baseline_profit),
    }


def _normalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(by_alias=True, exclude_none=False, mode="json"))
    if is_dataclass(value):
        return {field.name: _normalize(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _normalize(val) for key, val in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "__dict__"):
        return {
            str(key): _normalize(val)
            for key, val in sorted(vars(value).items(), key=lambda item: str(item[0]))
            if not key.startswith("_")
        }
    return value
