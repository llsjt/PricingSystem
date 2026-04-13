from decimal import Decimal
from typing import Any, Protocol


class CompetitorProvider(Protocol):
    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        ...
