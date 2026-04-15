from typing import Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CompetitorItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    competitor_name: str = Field(alias="competitorName")
    price: Decimal
    original_price: Decimal | None = Field(default=None, alias="originalPrice")
    sales_volume_hint: str | None = Field(default=None, alias="salesVolumeHint")
    promotion_tag: str | None = Field(default=None, alias="promotionTag")
    shop_type: str | None = Field(default=None, alias="shopType")
    source_platform: str = Field(alias="sourcePlatform")


class CompetitorQueryResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    source_status: Literal["OK", "EMPTY", "UNCONFIGURED", "FAILED"] = Field(alias="sourceStatus")
    source: str
    message: str = ""
    raw_item_count: int = Field(alias="rawItemCount")
    filtered_item_count: int = Field(default=0, alias="filteredItemCount")
    valid_competitor_count: int = Field(default=0, alias="validCompetitorCount")
    market_floor: Decimal | None = Field(default=None, alias="marketFloor")
    market_median: Decimal | None = Field(default=None, alias="marketMedian")
    market_ceiling: Decimal | None = Field(default=None, alias="marketCeiling")
    market_average: Decimal | None = Field(default=None, alias="marketAverage")
    data_quality: Literal["HIGH", "MEDIUM", "LOW"] = Field(default="LOW", alias="dataQuality")
    quality_reasons: list[str] = Field(default_factory=list, alias="qualityReasons")
    competitors: list[CompetitorItem] = Field(default_factory=list)
