"""Typed structures shared by the entity extraction pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class EntityType(str, Enum):
    """Canonical entity categories recognised by the system."""

    PERSON = "PERSON"
    ORGANISATION = "ORG"
    GEOGRAPHY = "GPE"
    POLICY = "POLICY"
    MINISTRY = "MINISTRY"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class DetectedEntity:
    """Representation of a single entity mention."""

    text: str
    start: int
    end: int
    label: EntityType
    confidence: float
    detector: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EntityExtractionResult:
    """Aggregated result returned for each processed document."""

    source_id: str
    source_type: str
    text_length: int
    entities: list[DetectedEntity]
    skipped: bool = False
    notes: Optional[str] = None


@dataclass(slots=True)
class ExtractionJob:
    """Job payload passed to the batch processor."""

    source_id: str
    source_type: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
