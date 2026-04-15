from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.competitor import CompetitorItem, CompetitorQueryResult
from app.services.competitor_providers.snapshot_provider import SnapshotCompetitorProvider
from app.services.competitor_service import CompetitorService


class _FakeSnapshotRepo:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def list_competitors(self, product_title: str | None, category_name: str | None) -> list[dict]:
        return list(self.rows)


class _FakeProvider:
    def __init__(self, result: dict):
        self.result = result

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict:
        return dict(self.result)


class _ExplodingProvider:
    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict:
        raise RuntimeError("boom")


class _CountingProvider:
    def __init__(self, result: dict):
        self.result = result
        self.calls = 0

    def fetch(
        self,
        *,
        product_id: int,
        product_title: str | None,
        category_name: str | None,
        current_price: Decimal,
    ) -> dict:
        self.calls += 1
        return dict(self.result)


def test_competitor_settings_defaults_to_simulation_source():
    settings = Settings.model_validate({"COMPETITOR_DATA_SOURCE": "simulation"})

    assert settings.competitor_data_source == "simulation"
    assert settings.validate_competitor_source() == []


def test_competitor_settings_rejects_removed_or_unknown_source_value():
    with pytest.raises(ValidationError):
        Settings.model_validate({"COMPETITOR_DATA_SOURCE": "legacy"})

    with pytest.raises(ValidationError):
        Settings.model_validate({"COMPETITOR_DATA_SOURCE": "simulaton"})


def test_competitor_query_result_uses_decimal_aliases():
    item = CompetitorItem.model_validate(
        {
            "competitorName": "Example Competitor A",
            "price": Decimal("19.80"),
            "originalPrice": Decimal("29.90"),
            "salesVolumeHint": "paid by 3200 users in 30 days",
            "promotionTag": "store discount",
            "shopType": "flagship",
            "sourcePlatform": "Taobao",
        }
    )
    result = CompetitorQueryResult.model_validate(
        {
            "sourceStatus": "OK",
            "source": "SNAPSHOT",
            "message": "snapshot loaded",
            "rawItemCount": 1,
            "filteredItemCount": 1,
            "validCompetitorCount": 1,
            "marketFloor": Decimal("19.80"),
            "marketMedian": Decimal("19.80"),
            "marketCeiling": Decimal("19.80"),
            "marketAverage": Decimal("19.80"),
            "dataQuality": "LOW",
            "qualityReasons": ["valid competitors < 3"],
            "competitors": [item.model_dump(by_alias=True)],
        }
    )

    assert item.model_dump(by_alias=True)["competitorName"] == "Example Competitor A"
    assert result.model_dump(by_alias=True)["marketMedian"] == Decimal("19.80")


def test_competitor_service_returns_snapshot_result_when_snapshot_exists():
    provider = SnapshotCompetitorProvider(
        repo=_FakeSnapshotRepo(
            [
                {
                    "competitorName": "Example Competitor A",
                    "price": Decimal("19.80"),
                    "originalPrice": Decimal("29.90"),
                    "salesVolumeHint": "paid by 3200 users in 30 days",
                    "promotionTag": "store discount",
                    "shopType": "flagship",
                    "sourcePlatform": "Taobao",
                }
            ]
        ),
        normalize_row=CompetitorService._normalize_row,
        build_fallback=CompetitorService._build_price_fallback_static,
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["source"] == "SNAPSHOT"
    assert result["rawItemCount"] == 1
    assert result["competitors"][0]["competitorName"] == "Example Competitor A"


def test_competitor_service_returns_simulation_fallback_when_snapshot_missing():
    provider = SnapshotCompetitorProvider(
        repo=_FakeSnapshotRepo([]),
        normalize_row=CompetitorService._normalize_row,
        build_fallback=CompetitorService._build_price_fallback_static,
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["source"] == "SIMULATION_FALLBACK"
    assert result["rawItemCount"] == 3
    assert result["competitors"][0]["promotionTag"] == "店铺满减"


def test_competitor_service_normalizes_malformed_provider_result():
    service = CompetitorService(
        data_source="simulation",
        providers={"simulation": _FakeProvider({"source": "SNAPSHOT"})},
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "SNAPSHOT"
    assert result["rawItemCount"] == 0
    assert service.get_competitors(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    ) == []


def test_competitor_service_returns_provider_failure_without_extra_fallback():
    service = CompetitorService(
        data_source="simulation",
        providers={
            "simulation": _FakeProvider(
                {
                    "sourceStatus": "FAILED",
                    "source": "SNAPSHOT",
                    "message": "snapshot unavailable",
                    "rawItemCount": 0,
                    "competitors": [],
                }
            )
        },
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "SNAPSHOT"
    assert result["competitors"] == []


def test_competitor_service_returns_failed_result_when_provider_raises_exception():
    service = CompetitorService(
        data_source="simulation",
        providers={"simulation": _ExplodingProvider()},
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "SIMULATION"
    assert result["rawItemCount"] == 0
    assert result["competitors"] == []
    assert "RuntimeError" in result["message"]


def test_competitor_service_does_not_cache_simulation_result():
    provider = _CountingProvider(
        {
            "sourceStatus": "OK",
            "source": "SNAPSHOT",
            "message": "snapshot loaded",
            "rawItemCount": 3,
            "competitors": [
                {
                    "competitorName": "Example Black Coffee",
                    "price": 39.9,
                    "originalPrice": None,
                    "salesVolumeHint": "100+ paid orders",
                    "promotionTag": None,
                    "shopType": "flagship",
                    "sourcePlatform": "Taobao",
                }
            ],
        }
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    first = service.get_competitor_result(
        product_id=1,
        product_title="cache validation keyword",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )
    second = service.get_competitor_result(
        product_id=2,
        product_title="cache validation keyword",
        category_name="beverage",
        current_price=Decimal("30.90"),
    )

    assert provider.calls == 2
    assert first["sourceStatus"] == "OK"
    assert second["sourceStatus"] == "OK"


def test_competitor_service_does_not_cache_failed_result():
    provider = _CountingProvider(
        {
            "sourceStatus": "FAILED",
            "source": "SNAPSHOT",
            "message": "snapshot unavailable",
            "rawItemCount": 0,
            "competitors": [],
        }
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    service.get_competitor_result(
        product_id=1,
        product_title="failed cache validation keyword",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )
    service.get_competitor_result(
        product_id=2,
        product_title="failed cache validation keyword",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )

    assert provider.calls == 2
