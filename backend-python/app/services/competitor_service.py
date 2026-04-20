import logging
from decimal import Decimal
from statistics import median
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.competitor import CompetitorQueryResult
from app.services.competitor_providers import (
    CompetitorProvider,
    TmallCsvCompetitorProvider,
    UnconfiguredCompetitorProvider,
)

logger = logging.getLogger(__name__)

QUALITY_REASON_CN = {
    "VALID COMPETITORS >= 5": "有效竞品数不少于5个",
    "VALID COMPETITORS >= 3": "有效竞品数达到3个",
    "VALID COMPETITORS < 3": "有效竞品数不足3个",
}


class CompetitorService:
    """Market intelligence service backed by the Tmall CSV index."""

    def __init__(
        self,
        *,
        data_source: str | None = None,
        providers: dict[str, CompetitorProvider] | None = None,
    ) -> None:
        settings = get_settings()
        self.data_source = data_source or settings.competitor_data_source

        default_providers: dict[str, CompetitorProvider] = {
            "tmall_csv": TmallCsvCompetitorProvider(
                sample_size=settings.competitor_csv_sample_size,
            ),
        }
        if providers:
            default_providers.update(providers)
        self.providers = default_providers

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

        quality_reasons = [_to_quality_reason_cn(item) for item in (enriched.get("qualityReasons") or [])]
        if valid_count >= 5:
            enriched.setdefault("dataQuality", "HIGH")
            quality_reasons.append("有效竞品数不少于5个")
        elif valid_count >= 3:
            enriched.setdefault("dataQuality", "MEDIUM")
            quality_reasons.append("有效竞品数达到3个")
        else:
            enriched.setdefault("dataQuality", "LOW")
            quality_reasons.append("有效竞品数不足3个")
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


def _to_quality_reason_cn(value: Any) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return QUALITY_REASON_CN.get(normalized.upper(), normalized)
