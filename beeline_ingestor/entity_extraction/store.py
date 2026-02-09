"""Persistence helpers for entity extraction results."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import uuid4

from sqlalchemy import select

from ..db import Database
from ..models import Entity, EntityMention
from .canonicalizer import CanonicalMatch, EntityCanonicalizer
from .datatypes import DetectedEntity, EntityType


class EntityStore:
    """Store canonical entities and mentions in the application database."""

    def __init__(self, database: Database, canonicalizer: EntityCanonicalizer | None = None):
        self.database = database
        self.canonicalizer = canonicalizer

    def _context(self, text: str, start: int, end: int, window: int = 80) -> str:
        if start is None or end is None or not text:
            return ""
        left = max(0, start - window)
        right = min(len(text), end + window)
        return text[left:right].strip()

    def persist(self, source_id: str, source_type: str, text: str, entities: Iterable[DetectedEntity]) -> None:
        entity_list = [entity for entity in entities if entity.label != EntityType.UNKNOWN]
        if not entity_list:
            return
        now = datetime.now(timezone.utc)

        with self.database.session() as session:
            for detected in entity_list:
                match = self.canonicalizer.resolve(session, detected) if self.canonicalizer else None
                entity = match.entity if match else self._build_entity_from_detection(detected, now)
                self._update_entity_metadata(entity, detected, now)
                session.add(entity)
                if match and match.alias_to_add and self.canonicalizer:
                    self.canonicalizer.add_alias(session, entity.id, match.alias_to_add, match.alias_source)

                mention = EntityMention(
                    id=uuid4().hex,
                    entity_id=entity.id,
                    source_type=source_type,
                    source_id=source_id,
                    text=detected.text.strip(),
                    start_offset=detected.start,
                    end_offset=detected.end,
                    confidence=detected.confidence,
                    detector=detected.detector,
                    context=self._context(text, detected.start, detected.end),
                    attributes=detected.metadata or {},
                )
                session.add(mention)

    def _build_entity_from_detection(self, detected: DetectedEntity, now: datetime) -> Entity:
        canonical = (detected.metadata.get("canonical_name") if detected.metadata else None) or detected.text
        canonical = canonical.strip()
        normalized = canonical.casefold()
        info = detected.metadata or {}
        return Entity(
            id=uuid4().hex,
            canonical_name=canonical,
            normalized_name=normalized,
            entity_type=detected.label.value,
            info=info,
            first_seen=now,
            last_seen=now,
        )

    def _update_entity_metadata(self, entity: Entity, detected: DetectedEntity, now: datetime) -> None:
        entity.last_seen = now
        if not entity.first_seen:
            entity.first_seen = now
        entity.mention_count = (entity.mention_count or 0) + 1
        if detected.metadata:
            merged = dict(entity.info or {})
            merged.update(detected.metadata)
            entity.info = merged
