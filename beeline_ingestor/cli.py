"""Command line entrypoints for the ingestion service."""
from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta

from .config import AppConfig
from .ingestion import IngestionPipeline
from .observability import init_sentry

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BeeLine ingestion pipeline")
    parser.add_argument("--since", help="ISO8601 timestamp to limit ingestion to newer items", default=None)
    parser.add_argument("--until", help="Optional ISO8601 timestamp to stop ingestion at", default=None)
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of feed entries to process")
    parser.add_argument("--source", default="rss", help="Label describing the run source (rss/backfill/manual)")
    parser.set_defaults(command="run")

    subparsers = parser.add_subparsers(dest="command")
    backfill = subparsers.add_parser("backfill", help="Run rolling historical ingestion windows")
    backfill.add_argument("--start", required=True, help="ISO8601 timestamp for the first window start")
    backfill.add_argument("--end", help="ISO8601 timestamp for the final window end (defaults to now)")
    backfill.add_argument("--window-days", type=int, default=7, help="Number of days per window")
    backfill.add_argument("--sleep-seconds", type=float, default=5.0, help="Delay between windows")
    backfill.add_argument("--limit", type=int, default=None, help="Optional per-window limit")

    return parser.parse_args()


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

    if args.command == "backfill":
        start = _parse_datetime(args.start)
        end = _parse_datetime(args.end) or datetime.now(timezone.utc)
        run_backfill_windows(
            pipeline,
            start=start,
            end=end,
            window_days=max(1, args.window_days),
            sleep_seconds=max(0.0, args.sleep_seconds),
            limit=args.limit,
        )
        return

    since_dt = _parse_datetime(args.since) or datetime.now(timezone.utc) - relativedelta(months=3)
    until_dt = _parse_datetime(args.until)
    result = pipeline.run(since=since_dt, until=until_dt, limit=args.limit, source=args.source)
    logger.info(
        "Run %s: total=%s inserted=%s updated=%s skipped=%s failed=%s",
        result.run_id,
        result.total_items,
        result.inserted,
        result.updated,
        result.skipped,
        result.failed,
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def run_backfill_windows(
    pipeline: IngestionPipeline,
    *,
    start: datetime,
    end: datetime,
    window_days: int,
    sleep_seconds: float,
    limit: int | None,
) -> None:
    """Iterate over a date range in fixed windows to backfill releases."""

    window = timedelta(days=window_days)
    current = start
    while current <= end:
        window_end = min(current + window, end)
        logger.info("Backfill window %s → %s", current.isoformat(), window_end.isoformat())
        pipeline.run(since=current, until=window_end, limit=limit, source="backfill")
        if window_end >= end:
            break
        current = window_end + timedelta(seconds=1)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()
