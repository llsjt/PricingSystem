from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.competitor import CompetitorItem, CompetitorQueryResult
from app.services.competitor_providers.tmall_csv_provider import TmallCsvCompetitorProvider
from app.services.competitor_service import CompetitorService


class _FakeCsvRepo:
    """In-memory stand-in for CompetitorCsvRepo used by tests."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.available = True

    def query_by_secondary_category(self, name: str, limit: int) -> list[dict]:
        return [r for r in self.rows if r.get("secondary_category") == name][:limit]

    def query_by_primary_category(self, name: str, limit: int) -> list[dict]:
        return [r for r in self.rows if r.get("primary_category") == name][:limit]

    def query_by_keyword(self, keyword: str, limit: int) -> list[dict]:
        kw = (keyword or "").lower()
        if not kw:
            return []
        return [
            r for r in self.rows
            if kw in (r.get("title") or "").lower() or kw in (r.get("short_title") or "").lower()
        ][:limit]


class _FakeProvider:
    def __init__(self, result: dict):
        self.result = result

    def fetch(self, **kwargs):
        return dict(self.result)


class _ExplodingProvider:
    def fetch(self, **kwargs):
        raise RuntimeError("boom")


def test_competitor_settings_defaults_to_tmall_csv_source():
    settings = Settings.model_validate({"COMPETITOR_DATA_SOURCE": "tmall_csv"})
    assert settings.competitor_data_source == "tmall_csv"
    assert settings.validate_competitor_source() == []


def test_competitor_settings_rejects_unknown_source_value():
    with pytest.raises(ValidationError):
        Settings.model_validate({"COMPETITOR_DATA_SOURCE": "legacy"})


def test_competitor_query_result_supports_new_breakdown_fields():
    item = CompetitorItem.model_validate(
        {
            "competitorName": "天猫超市",
            "price": Decimal("19.80"),
            "originalPrice": Decimal("29.90"),
            "salesVolumeHint": "年销量约1.2万件",
            "promotionTag": "满减",
            "shopType": "天猫超市",
            "sourcePlatform": "天猫",
        }
    )
    result = CompetitorQueryResult.model_validate(
        {
            "sourceStatus": "OK",
            "source": "TMALL_CSV",
            "message": "tmall csv match",
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
            "brandBreakdown": [
                {
                    "brand": "漫花",
                    "sampleCount": 3,
                    "averagePrice": 19.8,
                    "medianPrice": 19.8,
                    "minPrice": 18.0,
                    "maxPrice": 21.0,
                }
            ],
            "shopTypeBreakdown": [
                {"shopType": "天猫超市", "sampleCount": 3, "share": 0.6, "averagePrice": 19.8}
            ],
            "salesWeightedAverage": 19.5,
            "salesWeightedMedian": 19.6,
            "promotionDensity": {
                "promotionRate": 0.66,
                "averageDiscount": 0.7,
                "promotedSampleCount": 2,
            },
        }
    )

    dumped = result.model_dump(by_alias=True)
    assert dumped["source"] == "TMALL_CSV"
    assert dumped["brandBreakdown"][0]["brand"] == "漫花"
    assert dumped["shopTypeBreakdown"][0]["shopType"] == "天猫超市"
    assert dumped["salesWeightedAverage"] == 19.5
    assert dumped["promotionDensity"]["promotedSampleCount"] == 2


def test_tmall_csv_provider_matches_secondary_category_first():
    rows = [
        {
            "product_id": "p1",
            "brand": "漫花",
            "primary_category": "洗护",
            "secondary_category": "卷筒纸",
            "shop_name": "漫花官方",
            "shop_type": "旗舰店",
            "title": "漫花卷纸",
            "short_title": "漫花",
            "original_price": 39.9,
            "discount_price": 29.9,
            "final_price": 25.0,
            "yearly_sales": 7000,
            "promotion_tag": "满99减20",
        },
        {
            "product_id": "p2",
            "brand": "维达",
            "primary_category": "洗护",
            "secondary_category": "卷筒纸",
            "shop_name": "维达旗舰店",
            "shop_type": "旗舰店",
            "title": "维达卷纸",
            "short_title": "维达",
            "original_price": 49.9,
            "discount_price": 39.9,
            "final_price": 35.0,
            "yearly_sales": 12000,
            "promotion_tag": None,
        },
    ]
    provider = TmallCsvCompetitorProvider(repo=_FakeCsvRepo(rows), sample_size=5)

    result = provider.fetch(
        product_id=1, product_title="家用卷纸", category_name="卷筒纸", current_price=Decimal("30")
    )

    assert result["source"] == "TMALL_CSV"
    assert result["sourceStatus"] == "OK"
    assert result["rawItemCount"] == 2
    brands = {b["brand"] for b in result["brandBreakdown"]}
    assert brands == {"漫花", "维达"}
    assert result["salesWeightedAverage"] is not None
    assert result["promotionDensity"]["promotedSampleCount"] == 1
    shop_types = {s["shopType"] for s in result["shopTypeBreakdown"]}
    assert shop_types == {"旗舰店"}


def test_tmall_csv_provider_returns_unconfigured_when_index_missing():
    repo = _FakeCsvRepo(rows=[])
    repo.available = False
    provider = TmallCsvCompetitorProvider(repo=repo, sample_size=3)
    result = provider.fetch(
        product_id=1, product_title="x", category_name="y", current_price=Decimal("30")
    )
    assert result["source"] == "TMALL_CSV"
    assert result["sourceStatus"] == "UNCONFIGURED"
    assert result["rawItemCount"] == 0
    assert result["competitors"] == []


def test_tmall_csv_provider_returns_empty_when_no_match():
    provider = TmallCsvCompetitorProvider(repo=_FakeCsvRepo(rows=[]), sample_size=3)
    result = provider.fetch(
        product_id=1, product_title="未匹配标题", category_name="未匹配类目", current_price=Decimal("30")
    )
    assert result["source"] == "TMALL_CSV"
    assert result["sourceStatus"] == "EMPTY"
    assert result["competitors"] == []


def test_competitor_service_returns_failed_result_when_provider_raises_exception():
    service = CompetitorService(
        data_source="tmall_csv",
        providers={"tmall_csv": _ExplodingProvider()},
    )
    result = service.get_competitor_result(
        product_id=1,
        product_title="coffee",
        category_name="beverage",
        current_price=Decimal("29.90"),
    )
    assert result["sourceStatus"] == "FAILED"
    assert result["competitors"] == []
    assert "RuntimeError" in result["message"]


def test_competitor_service_passes_through_breakdown_fields():
    raw = {
        "sourceStatus": "OK",
        "source": "TMALL_CSV",
        "message": "tmall csv match",
        "rawItemCount": 2,
        "competitors": [
            {
                "competitorName": "店铺A",
                "price": 19.9,
                "originalPrice": 29.9,
                "salesVolumeHint": "年销量约1万件",
                "promotionTag": "满减",
                "shopType": "旗舰店",
                "sourcePlatform": "天猫",
            },
        ],
        "brandBreakdown": [
            {"brand": "A", "sampleCount": 1, "averagePrice": 19.9, "medianPrice": 19.9, "minPrice": 19.9, "maxPrice": 19.9}
        ],
        "shopTypeBreakdown": [
            {"shopType": "旗舰店", "sampleCount": 1, "share": 1.0, "averagePrice": 19.9}
        ],
        "salesWeightedAverage": 19.9,
        "salesWeightedMedian": 19.9,
        "promotionDensity": {"promotionRate": 1.0, "averageDiscount": 0.66, "promotedSampleCount": 1},
    }
    service = CompetitorService(
        data_source="tmall_csv",
        providers={"tmall_csv": _FakeProvider(raw)},
    )
    result = service.get_competitor_result(
        product_id=1, product_title="coffee", category_name="beverage", current_price=Decimal("29.9")
    )
    assert result["source"] == "TMALL_CSV"
    assert result["brandBreakdown"][0]["brand"] == "A"
    assert result["salesWeightedAverage"] == 19.9
    assert result["promotionDensity"]["promotedSampleCount"] == 1
