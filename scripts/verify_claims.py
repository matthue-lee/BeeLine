#!/usr/bin/env python
"""Re-run claim extraction + verification for stored summaries."""
from __future__ import annotations

import argparse

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.models import ReleaseDocument, Summary
from beeline_ingestor.schemas.summary import SummaryPayload
from beeline_ingestor.verification.service import VerificationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reprocess claim verification")
    parser.add_argument("--release-id", help="Specific release ID to reverify")
    parser.add_argument("--limit", type=int, default=25, help="Max number of releases to process")
    return parser.parse_args()


def build_payload(summary: Summary) -> SummaryPayload:
    data = {
        "release_id": summary.release_id,
        "summary_short": summary.summary_short,
        "summary_why_matters": summary.summary_why_matters,
        "claims": summary.claims or [],
    }
    return SummaryPayload.from_dict(data)


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    db = Database(config)
    db.create_all()
    verifier = VerificationService(config, db)

    with db.session() as session:
        query = session.query(Summary).join(ReleaseDocument, ReleaseDocument.id == Summary.release_id)
        if args.release_id:
            query = query.filter(Summary.release_id == args.release_id)
        else:
            query = query.order_by(Summary.created_at.desc()).limit(args.limit)
        rows = query.all()
        releases = {release.id: release for release in session.query(ReleaseDocument).filter(ReleaseDocument.id.in_([row.release_id for row in rows])).all()}

    for summary in rows:
        document = releases.get(summary.release_id)
        if not document:
            continue
        payload = build_payload(summary)
        verifier.process_summary(document, summary, payload)
        print(f"Reverified claims for release {summary.release_id}")


if __name__ == "__main__":
    main()
