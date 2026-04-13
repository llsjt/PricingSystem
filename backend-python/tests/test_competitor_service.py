import asyncio
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.competitor import CompetitorItem, CompetitorQueryResult


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


def test_startup_fails_when_competitor_source_is_misconfigured(monkeypatch):
    from app import main as app_main

    monkeypatch.setattr(
        app_main,
        "settings",
        Settings.model_validate(
            {
                "COMPETITOR_DATA_SOURCE": "taobao_h5",
                "TSDK_TAOBAO_COOKIE": "",
                "TSDK_TAOBAO_SEARCH_API_URL": "",
            }
        ),
    )
    monkeypatch.setattr(app_main, "ensure_agent_run_log_schema", lambda *_args, **_kwargs: None)

    class StubQueueService:
        async def start(self):
            raise AssertionError("queue start should not be reached")

        def recover_pending_tasks(self):
            raise AssertionError("queue recovery should not be reached")

    monkeypatch.setattr(app_main, "get_task_queue_service", lambda: StubQueueService())

    with pytest.raises(RuntimeError, match="TSDK_TAOBAO_COOKIE is required for taobao_h5"):
        asyncio.run(app_main.startup_migrations())
