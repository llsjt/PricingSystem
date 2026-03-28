import json
import re
from decimal import Decimal


def parse_constraints(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    constraints: dict[str, Decimal | bool | str] = {}

    min_profit = re.search(r"(?:利润率|毛利率)\D*(\d+(?:\.\d+)?)\s*%", text)
    if min_profit:
        constraints["min_profit_rate"] = Decimal(min_profit.group(1)) / Decimal("100")

    min_price = re.search(
        r"(?:最低(?:售价|价格|价)|售价不低于|价格不低于|最低售价不低于|最低价格不低于|最低价不低于)\D*(\d+(?:\.\d+)?)",
        text,
    )
    if min_price:
        constraints["min_price"] = Decimal(min_price.group(1))

    max_price = re.search(
        r"(?:最高(?:售价|价格|价)|售价不高于|价格不高于|最高售价不高于|最高价格不高于|最高价不高于)\D*(\d+(?:\.\d+)?)",
        text,
    )
    if max_price:
        constraints["max_price"] = Decimal(max_price.group(1))

    max_discount = re.search(r"(?:降价幅度|折扣|优惠)\D*(\d+(?:\.\d+)?)\s*%", text)
    if max_discount:
        constraints["max_discount_rate"] = Decimal(max_discount.group(1)) / Decimal("100")

    if "人工审核" in text:
        constraints["force_manual_review"] = True

    return constraints
