#!/usr/bin/env python
"""Generate summaries for releases in bulk."""
from __future__ import annotations

import argparse

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.models import ReleaseDocument
from beeline_ingestor.summarization.service import SummaryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate summaries for releases")
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    db = Database(config)
    db.create_all()
    service = SummaryService(config, db)
    processed = 0
    with db.session() as session:
        releases = (
            session.query(ReleaseDocument)
            .order_by(ReleaseDocument.published_at.desc().nullslast())
            .limit(args.limit)
            .all()
        )
    for release in releases:
        result = service.generate_if_needed(release)
        if result:
            processed += 1
    print(f"Generated summaries for {processed} releases")


if __name__ == "__main__":
    main()
