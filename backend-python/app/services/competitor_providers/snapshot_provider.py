from decimal import Decimal
from typing import Any, Callable

from app.repos.competitor_snapshot_repo import CompetitorSnapshotRepo


class SnapshotCompetitorProvider:
    def __init__(
        self,
        repo: CompetitorSnapshotRepo | None = None,
        *,
        normalize_row: Callable[[dict[str, Any]], dict[str, Any]],
        build_fallback: Callable[[Decimal], list[dict[str, Any]]],
    ) -> None:
        self.repo = repo or CompetitorSnapshotRepo()
        self.normalize_row = normalize_row
        self.build_fallback = build_fallback

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        rows = self.repo.list_competitors(product_title=product_title, category_name=category_name)
        if rows:
            return {
                "sourceStatus": "OK",
                "source": "SNAPSHOT",
                "message": "snapshot loaded",
                "rawItemCount": len(rows),
                "competitors": [self.normalize_row(row) for row in rows],
            }

        fallback = self.build_fallback(current_price)
        return {
            "sourceStatus": "OK",
            "source": "SIMULATION_FALLBACK",
            "message": "snapshot missing, fallback generated",
            "rawItemCount": len(fallback),
            "competitors": fallback,
        }
