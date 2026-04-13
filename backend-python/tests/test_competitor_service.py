from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.competitor import CompetitorItem, CompetitorQueryResult
from app.services.competitor_service import CompetitorService


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


def test_competitor_service_returns_full_result_for_simulation_source():
    service = CompetitorService.for_test(data_source="simulation")

    result = service.get_competitor_result(
        product_id=1,
        product_title="咖啡",
        category_name="饮品",
        current_price=Decimal("29.90"),
    )

    assert result["sourceStatus"] == "OK"
    assert result["source"] in {"SNAPSHOT", "SIMULATION_FALLBACK"}
    assert result["competitors"]


def test_competitor_service_does_not_fallback_to_snapshot_when_real_source_fails():
    service = CompetitorService.for_test(
        data_source="taobao_h5",
        provider_result={
            "sourceStatus": "FAILED",
            "source": "TAOBAO_H5",
            "message": "token expired",
            "rawItemCount": 0,
            "competitors": [],
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
