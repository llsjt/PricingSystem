import logging
from decimal import Decimal
from statistics import median
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.competitor import CompetitorQueryResult
from app.services.competitor_providers import (
    CompetitorProvider,
    SnapshotCompetitorProvider,
    UnconfiguredCompetitorProvider,
)

logger = logging.getLogger(__name__)


class CompetitorService:
    """Market intelligence service backed by simulation/snapshot data only."""

    def __init__(
        self,
        *,
        data_source: str | None = None,
        providers: dict[str, CompetitorProvider] | None = None,
    ) -> None:
        settings = get_settings()
        self.data_source = data_source or settings.competitor_data_source

        default_providers: dict[str, CompetitorProvider] = {
            "simulation": SnapshotCompetitorProvider(
                normalize_row=self._normalize_row,
                build_fallback=self._build_price_fallback_static,
            ),
        }
        if providers:
            default_providers.update(providers)
        self.providers = default_providers

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
            return UnconfiguredCompetitorProvider(
                source=str(self.data_source).upper(),
                message=f"unsupported competitor data source: {self.data_source}",
            )
        return provider

    @staticmethod
    def _safe_price(value: Any) -> float | None:
        try:
            if value is None:
                return None
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    def _enrich_result_metadata(self, raw_result: Any) -> dict[str, Any]:
        if not isinstance(raw_result, dict):
            return raw_result

        enriched = dict(raw_result)
        competitors = [item for item in enriched.get("competitors") or [] if isinstance(item, dict)]
        prices = [price for item in competitors if (price := self._safe_price(item.get("price"))) is not None]
        valid_count = len(prices)

        if prices:
            enriched.setdefault("marketFloor", round(min(prices), 2))
            enriched.setdefault("marketMedian", round(float(median(prices)), 2))
            enriched.setdefault("marketCeiling", round(max(prices), 2))
            enriched.setdefault("marketAverage", round(sum(prices) / len(prices), 2))
        else:
            enriched.setdefault("marketFloor", None)
            enriched.setdefault("marketMedian", None)
            enriched.setdefault("marketCeiling", None)
            enriched.setdefault("marketAverage", None)

        enriched.setdefault("filteredItemCount", len(competitors))
        enriched.setdefault("validCompetitorCount", valid_count)

        quality_reasons = list(enriched.get("qualityReasons") or [])
        if valid_count >= 5:
            enriched.setdefault("dataQuality", "HIGH")
            quality_reasons.append("valid competitors >= 5")
        elif valid_count >= 3:
            enriched.setdefault("dataQuality", "MEDIUM")
            quality_reasons.append("valid competitors >= 3")
        else:
            enriched.setdefault("dataQuality", "LOW")
            quality_reasons.append("valid competitors < 3")
        enriched.setdefault("qualityReasons", _unique(quality_reasons))
        return enriched

    def _normalize_result(self, raw_result: Any) -> dict[str, Any]:
        try:
            result = CompetitorQueryResult.model_validate(self._enrich_result_metadata(raw_result))
        except ValidationError:
            source = "UNKNOWN"
            if isinstance(raw_result, dict):
                source = str(raw_result.get("source") or self.data_source).upper()
            result = CompetitorQueryResult.model_validate(
                {
                    "sourceStatus": "FAILED",
                    "source": source,
                    "message": "provider returned invalid competitor result",
                    "rawItemCount": 0,
                    "competitors": [],
                }
            )
        return result.model_dump(by_alias=True)

    def _build_failed_result(self, *, source: str, message: str) -> dict[str, Any]:
        return CompetitorQueryResult.model_validate(
            {
                "sourceStatus": "FAILED",
                "source": source,
                "message": message,
                "rawItemCount": 0,
                "competitors": [],
            }
        ).model_dump(by_alias=True)

    def get_competitor_result(
        self,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict[str, Any]:
        provider = self._resolve_provider()
        try:
            raw_result = provider.fetch(
                product_id=product_id,
                product_title=product_title,
                category_name=category_name,
                current_price=current_price,
            )
        except Exception as exc:
            source = str(getattr(provider, "source", self.data_source)).upper()
            return self._build_failed_result(
                source=source,
                message=f"provider exception: {type(exc).__name__}: {exc}",
            )
        return self._normalize_result(raw_result)

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


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
