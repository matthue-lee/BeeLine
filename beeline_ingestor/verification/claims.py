"""Claim extraction and persistence helpers."""
from __future__ import annotations

from typing import Iterable, List

from ..db import Database
from ..models import Claim, Summary
from ..schemas.summary import SummaryPayload


class ClaimService:
    """Synchronise structured claims for summaries."""

    def __init__(self, database: Database):
        self.database = database

    def sync_from_payload(self, summary: Summary, payload: SummaryPayload) -> list[Claim]:
        """Replace claim rows for the given summary with the latest payload."""

        claims_data = payload.to_dict().get("claims", [])
        with self.database.session() as session:
            session.query(Claim).filter(Claim.summary_id == summary.id).delete()
            claim_rows: list[Claim] = []
            for idx, claim_json in enumerate(claims_data):
                claim = Claim(
                    summary_id=summary.id,
                    claim_index=idx,
                    text=claim_json.get("text", "").strip(),
                    category=claim_json.get("category"),
                    citations=claim_json.get("citations"),
                )
                session.add(claim)
                claim_rows.append(claim)
            session.flush()
            for claim in claim_rows:
                session.refresh(claim)
            return claim_rows

    def list_for_summary(self, summary: Summary) -> List[Claim]:
        with self.database.session() as session:
            rows = (
                session.query(Claim)
                .filter(Claim.summary_id == summary.id)
                .order_by(Claim.claim_index.asc())
                .all()
            )
            return rows
