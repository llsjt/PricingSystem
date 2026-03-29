import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class CompetitorSnapshotRepo:
    """模拟竞品数据仓储，后续可替换为真实竞品接口实现。"""

    def __init__(self) -> None:
        self.dataset_path = Path(__file__).resolve().parents[1] / "data" / "competitor_snapshots.json"

    @lru_cache(maxsize=1)
    def _load_dataset(self) -> dict[str, Any]:
        text = self.dataset_path.read_text(encoding="utf-8")
        return json.loads(text)

    def find_snapshot(self, product_title: str | None, category_name: str | None) -> dict[str, Any] | None:
        dataset = self._load_dataset()
        snapshots = dataset.get("snapshots", [])
        title = (product_title or "").strip().lower()
        category = (category_name or "").strip().lower()

        for snapshot in snapshots:
            keywords = [str(item).strip().lower() for item in snapshot.get("keywords", []) if str(item).strip()]
            snapshot_category = str(snapshot.get("category", "")).strip().lower()
            if category and snapshot_category and category in snapshot_category:
                return snapshot
            if title and any(keyword and keyword in title for keyword in keywords):
                return snapshot

        return snapshots[0] if snapshots else None

    def list_competitors(self, product_title: str | None, category_name: str | None) -> list[dict[str, Any]]:
        snapshot = self.find_snapshot(product_title, category_name)
        if not snapshot:
            return []
        raw = snapshot.get("competitors", [])
        return [item for item in raw if isinstance(item, dict)]
