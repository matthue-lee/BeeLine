#!/usr/bin/env python
"""Manual override for summaries."""
from __future__ import annotations

import argparse

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.models import Summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Override summary text")
    parser.add_argument("release_id")
    parser.add_argument("summary_short")
    parser.add_argument("--why", dest="summary_why_matters")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    db = Database(config)
    with db.session() as session:
        summary = session.query(Summary).where(Summary.release_id == args.release_id).one_or_none()
        if not summary:
            raise SystemExit(f"No summary found for release {args.release_id}")
        summary.summary_short = args.summary_short
        summary.summary_why_matters = args.summary_why_matters
        print(f"Updated summary for {args.release_id}")


if __name__ == "__main__":
    main()
