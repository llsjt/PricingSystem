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


def test_competitor_settings_defaults_to_simulation_source():
    settings = Settings.model_validate({})

    assert settings.competitor_data_source == "simulation"
    assert settings.validate_competitor_source() == []


def test_competitor_settings_validate_taobao_source_requirements():
    settings = Settings.model_validate(
        {
            "COMPETITOR_DATA_SOURCE": "taobao_h5",
            "TSDK_TAOBAO_COOKIE": "",
            "TSDK_TAOBAO_SEARCH_API_URL": "",
        }
    )

    errors = settings.validate_competitor_source()

    assert errors == [
        "TSDK_TAOBAO_COOKIE is required for taobao_h5",
        "TSDK_TAOBAO_SEARCH_API_URL is required for taobao_h5",
    ]


def test_competitor_settings_rejects_unknown_source_value():
    with pytest.raises(ValidationError):
        Settings.model_validate({"COMPETITOR_DATA_SOURCE": "simulaton"})


def test_competitor_query_result_uses_decimal_aliases():
    item = CompetitorItem.model_validate(
        {
            "competitorName": "晨曦工坊旗舰店",
            "price": Decimal("19.80"),
            "originalPrice": Decimal("29.90"),
            "salesVolumeHint": "近30天销量约3200",
            "promotionTag": "店铺满减",
            "shopType": "旗舰店",
            "sourcePlatform": "淘宝",
        }
    )
    result = CompetitorQueryResult.model_validate(
        {
            "sourceStatus": "OK",
            "source": "simulation",
            "message": "snapshot loaded",
            "rawItemCount": 1,
            "competitors": [item.model_dump(by_alias=True)],
        }
    )

    assert item.model_dump(by_alias=True) == {
        "competitorName": "晨曦工坊旗舰店",
        "price": Decimal("19.80"),
        "originalPrice": Decimal("29.90"),
        "salesVolumeHint": "近30天销量约3200",
        "promotionTag": "店铺满减",
        "shopType": "旗舰店",
        "sourcePlatform": "淘宝",
    }
    assert result.model_dump(by_alias=True) == {
        "sourceStatus": "OK",
        "source": "simulation",
        "message": "snapshot loaded",
        "rawItemCount": 1,
        "competitors": [
            {
                "competitorName": "晨曦工坊旗舰店",
                "price": Decimal("19.80"),
                "originalPrice": Decimal("29.90"),
                "salesVolumeHint": "近30天销量约3200",
                "promotionTag": "店铺满减",
                "shopType": "旗舰店",
                "sourcePlatform": "淘宝",
            }
        ],
    }


def test_competitor_service_returns_snapshot_result_when_snapshot_exists():
    provider = SnapshotCompetitorProvider(
        repo=_FakeSnapshotRepo(
            [
                {
                    "competitorName": "晨曦工坊旗舰店",
                    "price": Decimal("19.80"),
                    "originalPrice": Decimal("29.90"),
                    "salesVolumeHint": "近30天销量约3200",
                    "promotionTag": "店铺满减",
                    "shopType": "旗舰店",
                    "sourcePlatform": "淘宝",
                }
            ]
        ),
        normalize_row=CompetitorService._normalize_row,
        build_fallback=CompetitorService._build_price_fallback_static,
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["source"] == "SNAPSHOT"
    assert result["rawItemCount"] == 1
    assert result["competitors"][0]["competitorName"] == "晨曦工坊旗舰店"


def test_competitor_service_returns_simulation_fallback_when_snapshot_missing():
    provider = SnapshotCompetitorProvider(
        repo=_FakeSnapshotRepo([]),
        normalize_row=CompetitorService._normalize_row,
        build_fallback=CompetitorService._build_price_fallback_static,
    )
    service = CompetitorService(data_source="simulation", providers={"simulation": provider})

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["source"] == "SIMULATION_FALLBACK"
    assert result["rawItemCount"] == 3
    assert result["competitors"][0]["promotionTag"] == "店铺满减"


def test_competitor_service_returns_structured_result_when_taobao_provider_is_unconfigured():
    service = CompetitorService(data_source="taobao_h5")

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "UNCONFIGURED"
    assert result["source"] == "TAOBAO_H5"
    assert result["rawItemCount"] == 0
    assert result["competitors"] == []


def test_competitor_service_normalizes_malformed_provider_result():
    service = CompetitorService(
        data_source="taobao_h5",
        providers={"taobao_h5": _FakeProvider({"source": "TAOBAO_H5"})},
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "TAOBAO_H5"
    assert result["rawItemCount"] == 0
    assert service.get_competitors(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    ) == []


def test_competitor_service_does_not_fallback_to_snapshot_when_real_source_fails():
    service = CompetitorService(
        data_source="taobao_h5",
        providers={
            "taobao_h5": _FakeProvider(
                {
                    "sourceStatus": "FAILED",
                    "source": "TAOBAO_H5",
                    "message": "token expired",
                    "rawItemCount": 0,
                    "competitors": [],
                }
            )
        },
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "TAOBAO_H5"
    assert result["competitors"] == []


def test_competitor_service_returns_failed_result_when_provider_raises_exception():
    service = CompetitorService(
        data_source="taobao_h5",
        providers={"taobao_h5": _ExplodingProvider()},
    )

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "FAILED"
    assert result["source"] == "TAOBAO_H5"
    assert result["rawItemCount"] == 0
    assert result["competitors"] == []
    assert "RuntimeError" in result["message"]
