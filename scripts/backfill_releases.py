#!/usr/bin/env python
"""Helper script to run rolling backfill ingestion windows."""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor import cli
from beeline_ingestor.config import AppConfig
from beeline_ingestor.ingestion import IngestionPipeline
from beeline_ingestor.observability import init_sentry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Beehive releases in monthly windows")
    parser.add_argument(
        "--start",
        help="ISO8601 timestamp to begin backfill (defaults to first day of previous year)",
        default=None,
    )
    parser.add_argument("--end", help="ISO8601 timestamp to finish backfill (defaults to now)")
    parser.add_argument("--window-days", type=int, default=30, help="Days per window (default ~1 month)")
    parser.add_argument("--sleep-seconds", type=float, default=5.0, help="Delay between windows")
    parser.add_argument("--limit", type=int, default=None, help="Optional per-window feed entry cap")
    return parser.parse_args()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def default_start_start_of_last_year() -> datetime:
    return datetime(2023, 11, 29, tzinfo=timezone.utc)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    args = parse_args()
    config = AppConfig.from_env()
    init_sentry(
        config.sentry_dsn,
        environment=config.sentry_environment,
        traces_sample_rate=config.sentry_traces_sample_rate,
        profiles_sample_rate=config.sentry_profiles_sample_rate,
    )
    pipeline = IngestionPipeline(config)

    start = parse_datetime(args.start)
    if not start:
        start = default_start_start_of_last_year()
    end = parse_datetime(args.end) or datetime.now(timezone.utc)

    cli.run_backfill_windows(
        pipeline,
        start=start,
        end=end,
        window_days=max(1, args.window_days),
        sleep_seconds=max(0.0, args.sleep_seconds),
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
