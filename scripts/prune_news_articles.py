"""Delete news articles older than the configured retention window."""
from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from beeline_ingestor.config import AppConfig
from beeline_ingestor.crosslink.articles import NewsArticleRepository
from beeline_ingestor.db import Database


def main() -> None:
    config = AppConfig.from_env()
    db = Database(config)
    db.create_all()
    repo = NewsArticleRepository(db)
    removed = repo.prune(config.crosslink.retention_days)
    print(f"Removed {removed} news articles older than {config.crosslink.retention_days} days")


if __name__ == "__main__":
    main()
