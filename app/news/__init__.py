"""News collection and enrichment services."""

from .search import NewsCollector, collect_news

__all__ = ["NewsCollector", "collect_news"]
