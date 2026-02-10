"""Guardrails for summary payloads."""
from __future__ import annotations

from typing import List

from ..schemas.summary import SummaryPayload

BANNED_PHRASES: List[str] = [
    "may be",
    "could be",
    "might",
    "hopefully",
]


def apply_guardrails(payload: SummaryPayload) -> SummaryPayload:
    text = _clean_text(payload.summary_short)
    why = _clean_text(payload.summary_why_matters) if payload.summary_why_matters else None
    payload.summary_short = text or payload.summary_short
    payload.summary_why_matters = why or payload.summary_why_matters
    return payload


def _clean_text(value: str | None) -> str | None:
    if not value:
        return value
    cleaned = value.strip()
    for phrase in BANNED_PHRASES:
        cleaned = cleaned.replace(phrase, "")
    return cleaned.strip()
