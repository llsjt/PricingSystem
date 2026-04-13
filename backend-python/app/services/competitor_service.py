from decimal import Decimal
from typing import Any

from app.core.config import get_settings
from app.services.competitor_providers import CompetitorProvider, SnapshotCompetitorProvider


class CompetitorService:
    """Market intelligence service with configurable competitor data providers."""

    def __init__(
        self,
        *,
        data_source: str | None = None,
        providers: dict[str, CompetitorProvider] | None = None,
    ) -> None:
        self.data_source = data_source or get_settings().competitor_data_source
        self.providers = providers or {
            "simulation": SnapshotCompetitorProvider(
                normalize_row=self._normalize_row,
                build_fallback=self._build_price_fallback_static,
            )
        }

    @classmethod
    def for_test(
        cls,
        *,
        data_source: str,
        provider_result: dict[str, Any] | None = None,
    ) -> "CompetitorService":
        providers: dict[str, CompetitorProvider] = {
            "simulation": SnapshotCompetitorProvider(
                normalize_row=cls._normalize_row,
                build_fallback=cls._build_price_fallback_static,
            )
        }
        if provider_result is not None:
            providers[data_source] = _StaticCompetitorProvider(provider_result)
        return cls(data_source=data_source, providers=providers)

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

    @staticmethod
    def _build_price_fallback_static(current_price: Decimal) -> list[dict[str, Any]]:
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
                "promotionTag": "直播专享价",
                "shopType": None,
                "sourcePlatform": "抖音",
            },
        ]

    def _resolve_provider(self) -> CompetitorProvider:
        provider = self.providers.get(self.data_source)
        if provider is None:
            raise ValueError(f"Unsupported competitor data source: {self.data_source}")
        return provider

    def get_competitor_result(
        self,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        result = self._resolve_provider().fetch(
            product_id=product_id,
            product_title=product_title,
            category_name=category_name,
            current_price=current_price,
        )
        competitors = result.get("competitors", [])
        for item in competitors:
            item["sourceProductId"] = product_id
        return result

    def get_competitors(
        self,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> list[dict[str, Any]]:
        return self.get_competitor_result(
            product_id=product_id,
            product_title=product_title,
            category_name=category_name,
            current_price=current_price,
        )["competitors"]


class _StaticCompetitorProvider:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        return dict(self.result)
