"""Simple dataclasses for summary payloads."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class ClaimPayload:
    text: str
    citations: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.text or len(self.text.split()) < 3:
            raise ValueError("Claim text too short")


@dataclass
class SummaryPayload:
    release_id: str
    summary_short: str
    summary_why_matters: Optional[str] = None
    claims: List[ClaimPayload] = field(default_factory=list)

    def validate(self) -> None:
        if not self.summary_short or len(self.summary_short.split()) < 5:
            raise ValueError("summary_short too short")
        for claim in self.claims:
            claim.validate()

    def to_dict(self) -> dict:
        return {
            "release_id": self.release_id,
            "summary_short": self.summary_short,
            "summary_why_matters": self.summary_why_matters,
            "claims": [asdict(claim) for claim in self.claims],
        }
