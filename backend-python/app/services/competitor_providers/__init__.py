"""竞品提供者包入口，统一暴露竞品来源实现。"""

from app.services.competitor_providers.base import CompetitorProvider, UnconfiguredCompetitorProvider
from app.services.competitor_providers.tmall_csv_provider import TmallCsvCompetitorProvider

__all__ = ["CompetitorProvider", "TmallCsvCompetitorProvider", "UnconfiguredCompetitorProvider"]
