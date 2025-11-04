"""Command line entrypoints for the ingestion service."""
from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from .config import AppConfig
from .ingestion import IngestionPipeline

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BeeLine ingestion pipeline")
    parser.add_argument("--since", help="ISO8601 timestamp to limit ingestion to newer items", default=None)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = parse_args()
    config = AppConfig.from_env()
    pipeline = IngestionPipeline(config)

    since_dt = None
    if args.since:
        since_dt = datetime.fromisoformat(args.since)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)

    result = pipeline.run(since=since_dt)
    logger.info(
        "Run %s: total=%s inserted=%s updated=%s skipped=%s failed=%s",
        result.run_id,
        result.total_items,
        result.inserted,
        result.updated,
        result.skipped,
        result.failed,
    )


if __name__ == "__main__":
    main()
