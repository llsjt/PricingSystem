"""数学工具模块，集中处理金额、比例和数值安全计算。"""

from decimal import Decimal, ROUND_HALF_UP


def money(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.00")
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ratio(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0.0000")
    return Decimal(str(value)).quantize(Decimal("0.0000"), rounding=ROUND_HALF_UP)


def clamp_decimal(value: Decimal, floor: Decimal, ceiling: Decimal) -> Decimal:
    if value < floor:
        return floor
    if value > ceiling:
        return ceiling
    return value
