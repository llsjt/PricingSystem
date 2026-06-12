"""Shared Agent role metadata used by orchestration and output mapping."""

from __future__ import annotations

from typing import Any

AGENT_META: list[dict[str, Any]] = [
    {"code": "DATA_ANALYSIS", "name": "数据分析Agent", "order": 1},
    {"code": "MARKET_INTEL", "name": "市场情报Agent", "order": 2},
    {"code": "RISK_CONTROL", "name": "风险控制Agent", "order": 3},
    {"code": "MANAGER_COORDINATOR", "name": "经理协调Agent", "order": 4},
]

ANALYSIS_ORDERS = (1, 2, 3)
MANAGER_ORDER = 4

AGENT_KIND_BY_CODE = {
    "DATA_ANALYSIS": "PRICE_PROPOSAL",
    "MARKET_INTEL": "MARKET_ASSESSMENT",
    "RISK_CONTROL": "RISK_ASSESSMENT",
    "MANAGER_COORDINATOR": "ARBITRATION",
}


def get_agent_meta(order: int) -> dict[str, Any]:
    return AGENT_META[order - 1]

