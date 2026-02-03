"""Validation helpers to reduce false positives from extraction."""
from __future__ import annotations

import re
from typing import Iterable, List

from .config import EntityExtractionConfig
from .datatypes import DetectedEntity


MONTHS = {
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
}


class EntityValidator:
    """Apply rule-based filters over detected entities."""

    SENTENCE_BOUNDARY = re.compile(r"^[\.!?\s]+$")

    def __init__(self, config: EntityExtractionConfig):
        self.config = config

    def is_valid(self, entity: DetectedEntity) -> bool:
        text = entity.text.strip()
        if len(text) < self.config.min_entity_length:
            return False
        lowered = text.casefold()
        if lowered in MONTHS:
            return False
        if self.config.is_blocklisted(text):
            return False
        if entity.confidence < self.config.min_confidence:
            return False
        if text.isupper() and len(text) > 4:
            return False
        if re.fullmatch(r"[\d\-/]+", text):
            return False
        if self.SENTENCE_BOUNDARY.match(text):
            return False
        return True

    def deduplicate(self, entities: Iterable[DetectedEntity]) -> list[DetectedEntity]:
        """Return entities without duplicates, prioritising higher confidence."""

        by_key: dict[tuple[int, int, str], DetectedEntity] = {}
        for entity in entities:
            key = (entity.start, entity.end, entity.text.casefold())
            existing = by_key.get(key)
            if not existing or entity.confidence > existing.confidence:
                by_key[key] = entity
        return list(by_key.values())

    def filter_entities(self, entities: Iterable[DetectedEntity]) -> list[DetectedEntity]:
        return self.deduplicate(entity for entity in entities if self.is_valid(entity))
