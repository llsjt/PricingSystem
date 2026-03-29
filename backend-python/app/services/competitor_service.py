from decimal import Decimal
from typing import Any

from app.repos.competitor_snapshot_repo import CompetitorSnapshotRepo


class CompetitorService:
    """市场情报层：统一提供模拟竞品数据，避免 Agent prompt 内硬编码。"""

    def __init__(self) -> None:
        self.repo = CompetitorSnapshotRepo()

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "competitorName": str(row.get("competitorName") or "未知竞品"),
            "price": float(Decimal(str(row.get("price", 0))).quantize(Decimal("0.01"))),
            "originalPrice": (
                float(Decimal(str(row["originalPrice"])).quantize(Decimal("0.01")))
                if row.get("originalPrice") is not None
                else None
            ),
            "salesVolumeHint": str(row.get("salesVolumeHint") or "销量数据暂缺"),
            "promotionTag": str(row.get("promotionTag") or "常规促销"),
            "shopType": str(row.get("shopType") or "") or None,
            "sourcePlatform": str(row.get("sourcePlatform") or "综合平台"),
        }

    def _build_price_fallback(self, current_price: Decimal) -> list[dict[str, Any]]:
        base = Decimal(str(current_price or 0))
        if base <= 0:
            base = Decimal("99.00")
        return [
            {
                "competitorName": "同类旗舰店A",
                "price": float((base * Decimal("0.95")).quantize(Decimal("0.01"))),
                "originalPrice": float((base * Decimal("1.08")).quantize(Decimal("0.01"))),
                "salesVolumeHint": "近30天销量约3200",
                "promotionTag": "店铺满减",
                "shopType": "旗舰店",
                "sourcePlatform": "天猫",
            },
            {
                "competitorName": "同类优选店B",
                "price": float((base * Decimal("0.91")).quantize(Decimal("0.01"))),
                "originalPrice": None,
                "salesVolumeHint": "近30天销量约4600",
                "promotionTag": "限时直降",
                "shopType": "企业店",
                "sourcePlatform": "京东",
            },
            {
                "competitorName": "同类工厂店C",
                "price": float((base * Decimal("0.88")).quantize(Decimal("0.01"))),
                "originalPrice": float((base * Decimal("1.00")).quantize(Decimal("0.01"))),
                "salesVolumeHint": "近30天销量约5800",
                "promotionTag": "直播专享券",
                "shopType": None,
                "sourcePlatform": "抖音",
            },
        ]

    def get_competitors(
        self,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> list[dict[str, Any]]:
        rows = self.repo.list_competitors(product_title=product_title, category_name=category_name)
        if not rows:
            return self._build_price_fallback(current_price)

        normalized = [self._normalize_row(item) for item in rows]
        for item in normalized:
            item["sourceProductId"] = product_id
        return normalized
