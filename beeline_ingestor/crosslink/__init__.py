"""Cross-source article ingestion and linking utilities."""
from __future__ import annotations

from typing import TYPE_CHECKING

from .linker import CrossLinker

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from .news_ingestor import NewsIngestor as _NewsIngestor

__all__ = ["CrossLinker", "NewsIngestor"]  # pylint: disable=undefined-all-variable


def __getattr__(name: str):  # pragma: no cover - thin indirection
    if name == "NewsIngestor":
        from .news_ingestor import NewsIngestor as _NewsIngestor

        return _NewsIngestor
    raise AttributeError(name)
