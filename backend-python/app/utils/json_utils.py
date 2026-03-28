from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_json_compatible(value: Any) -> Any:
    """将任意对象转换成可落库到 JSON 字段的结构。"""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        # 日志场景下保留可读性，避免二进制浮点噪音
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_json_compatible(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_compatible(item) for item in value]
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json", by_alias=True)  # type: ignore[attr-defined]
            return to_json_compatible(dumped)
        except Exception:
            return str(value)
    return str(value)
