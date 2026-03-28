class CompetitorCrawlerTool:
    """Simulated crawler output; deliberately no real network crawling."""

    def fetch_details(self, search_hits: list[dict]) -> list[dict]:
        enriched: list[dict] = []
        for idx, item in enumerate(search_hits, start=1):
            enriched.append(
                {
                    **item,
                    "title": f"{item['category']}-竞品样本{idx}",
                    "monthly_sales": 120 + idx * 15,
                    "rating": 4.6 + (idx % 3) * 0.1,
                    "promo_intensity": "HIGH" if idx % 2 == 0 else "MEDIUM",
                }
            )
        return enriched

