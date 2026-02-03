"""Cross-source article ingestion and linking utilities."""

from .linker import CrossLinker
from .news_ingestor import NewsIngestor

__all__ = ["CrossLinker", "NewsIngestor"]
