"""Simple dataclasses for summary payloads."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, List, Optional


@dataclass
class ClaimPayload:
    text: str
    citations: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.text or len(self.text.split()) < 3:
            raise ValueError("Claim text too short")
        if self.citations and not all(isinstance(ref, str) and ref.strip() for ref in self.citations):
            raise ValueError("citations must be non-empty strings")

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "ClaimPayload":
        text = payload.get("text", "").strip()
        citations_raw = payload.get("citations") or []
        if isinstance(citations_raw, str):
            citations = [citations_raw]
        else:
            citations = [str(ref).strip() for ref in list(citations_raw) if str(ref).strip()]
        return cls(text=text, citations=citations)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "citations": list(self.citations)}


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
            "claims": [claim.to_dict() for claim in self.claims],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SummaryPayload":
        claims_raw: Iterable[dict[str, Any]] = payload.get("claims") or []
        claims = [ClaimPayload.from_raw(item) for item in claims_raw]
        instance = cls(
            release_id=str(payload.get("release_id") or "").strip(),
            summary_short=(payload.get("summary_short") or "").strip(),
            summary_why_matters=(payload.get("summary_why_matters") or None),
            claims=claims,
        )
        instance.validate()
        return instance
