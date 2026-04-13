from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompetitorItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    competitor_name: str = Field(alias="competitorName")
    price: float
    original_price: float | None = Field(default=None, alias="originalPrice")
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
    competitors: list[CompetitorItem] = Field(default_factory=list)
