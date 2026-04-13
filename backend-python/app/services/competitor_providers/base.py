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


class UnconfiguredCompetitorProvider:
    def __init__(self, *, source: str, message: str) -> None:
        self.source = source
        self.message = message

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        return {
            "sourceStatus": "UNCONFIGURED",
            "source": self.source,
            "message": self.message,
            "rawItemCount": 0,
            "competitors": [],
        }
