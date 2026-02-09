"""Canonical entity matching pipeline for Day 3-4."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Entity, EntityAlias
from .config import EntityExtractionConfig
from .datatypes import DetectedEntity, EntityType


@dataclass(slots=True)
class AuthorityRecord:
    canonical_name: str
    entity_type: str
    aliases: List[str]
    metadata: Dict[str, object]

    @property
    def normalized(self) -> str:
        return self.canonical_name.casefold().strip()


@dataclass(slots=True)
class CanonicalMatch:
    entity: Entity
    alias_to_add: Optional[str] = None
    alias_source: str = "detector"


class EntityCanonicalizer:
    """Resolve detected entities to canonical records using multi-stage matching."""

    def __init__(self, config: EntityExtractionConfig):
        self.config = config
        self.authority_records: list[AuthorityRecord] = self._load_authority_records(
            config.resources_dir / "canonical_entities.json"
        )
        self.authority_lookup: dict[tuple[str, str], AuthorityRecord] = {}
        for record in self.authority_records:
            key = (record.entity_type, record.normalized)
            self.authority_lookup[key] = record
            for alias in record.aliases:
                normalized_alias = alias.casefold().strip()
                self.authority_lookup[(record.entity_type, normalized_alias)] = record

    def _load_authority_records(self, path: Path) -> list[AuthorityRecord]:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        records: list[AuthorityRecord] = []
        for entry in data:
            records.append(
                AuthorityRecord(
                    canonical_name=entry["canonical_name"],
                    entity_type=entry["entity_type"],
                    aliases=list(entry.get("aliases", [])),
                    metadata=entry.get("metadata", {}),
                )
            )
        return records

    def resolve(self, session: Session, detected: DetectedEntity) -> Optional[CanonicalMatch]:
        normalized = self._normalize(detected.text)
        entity_type = detected.label.value

        authority_match = self._match_authority(session, entity_type, normalized, detected)
        if authority_match:
            return authority_match

        entity = session.execute(
            select(Entity).where(
                Entity.entity_type == entity_type,
                Entity.normalized_name == normalized,
            )
        ).scalar_one_or_none()
        if entity:
            alias = detected.text if normalized != entity.normalized_name else None
            return CanonicalMatch(entity=entity, alias_to_add=alias, alias_source="exact")

        alias_match = self._match_existing_alias(session, entity_type, normalized, detected.text)
        if alias_match:
            return alias_match

        fuzzy_match = self._fuzzy_match(session, entity_type, normalized, detected)
        if fuzzy_match:
            return fuzzy_match

        return None

    def add_alias(self, session: Session, entity_id: str, alias: str, source: str) -> None:
        normalized_alias = self._normalize(alias)
        if not normalized_alias:
            return
        exists = session.execute(
            select(EntityAlias).where(
                EntityAlias.entity_id == entity_id,
                EntityAlias.normalized_alias == normalized_alias,
            )
        ).scalar_one_or_none()
        if exists:
            return
        conflict = session.execute(
            select(EntityAlias).where(EntityAlias.normalized_alias == normalized_alias, EntityAlias.entity_id != entity_id)
        ).scalar_one_or_none()
        if conflict:
            return
        session.add(
            EntityAlias(
                entity_id=entity_id,
                alias=alias.strip(),
                normalized_alias=normalized_alias,
                source=source,
            )
        )

    # ---- internal helpers -------------------------------------------------

    def _match_authority(
        self, session: Session, entity_type: str, normalized: str, detected: DetectedEntity
    ) -> Optional[CanonicalMatch]:
        record = self.authority_lookup.get((entity_type, normalized))
        if not record:
            return None
        entity = session.execute(
            select(Entity).where(
                Entity.entity_type == entity_type,
                Entity.normalized_name == record.normalized,
            )
        ).scalar_one_or_none()
        if entity is None:
            entity = Entity(
                id=uuid4().hex,
                canonical_name=record.canonical_name,
                normalized_name=record.normalized,
                entity_type=entity_type,
                info=record.metadata,
                verified=True,
            )
        else:
            merged_info = dict(entity.info or {})
            merged_info.update(record.metadata)
            entity.info = merged_info
            entity.verified = True
        alias = detected.text if self._normalize(record.canonical_name) != normalized else None
        return CanonicalMatch(entity=entity, alias_to_add=alias, alias_source="authority")

    def _match_existing_alias(
        self, session: Session, entity_type: str, normalized: str, raw_text: str
    ) -> Optional[CanonicalMatch]:
        alias_row = session.execute(
            select(EntityAlias, Entity)
            .join(Entity, EntityAlias.entity_id == Entity.id)
            .where(
                EntityAlias.normalized_alias == normalized,
                Entity.entity_type == entity_type,
            )
        ).first()
        if not alias_row:
            return None
        entity = alias_row[1]
        alias = raw_text if normalized != entity.normalized_name else None
        return CanonicalMatch(entity=entity, alias_to_add=alias, alias_source="alias")

    def _fuzzy_match(
        self, session: Session, entity_type: str, normalized: str, detected: DetectedEntity
    ) -> Optional[CanonicalMatch]:
        threshold = self.config.canonical_fuzzy_threshold
        candidates: list[tuple[str, str, Optional[dict]]] = []
        for record in self.authority_records:
            if record.entity_type == entity_type:
                candidates.append((record.canonical_name, record.normalized, record.metadata))
        stmt = (
            select(Entity)
            .where(Entity.entity_type == entity_type)
            .order_by(Entity.mention_count.desc())
            .limit(self.config.canonical_max_candidates)
        )
        for entity in session.execute(stmt).scalars():
            candidates.append((entity.canonical_name, entity.normalized_name, entity.info))

        best_score = 0.0
        best_candidate: Optional[tuple[str, str, Optional[dict]]] = None
        target = self._strip_non_alnum(normalized)
        context_hint = self._context_hint(detected)

        for canonical_name, normalized_name, metadata in candidates:
            candidate_token = self._strip_non_alnum(normalized_name)
            if not candidate_token:
                continue
            score = SequenceMatcher(None, target, candidate_token).ratio()
            if context_hint and metadata:
                score += self._context_bonus(context_hint, metadata)
            if score > best_score:
                best_score = score
                best_candidate = (canonical_name, normalized_name, metadata)

        if not best_candidate or best_score < threshold:
            return None

        canonical_name, normalized_name, metadata = best_candidate
        entity = session.execute(
            select(Entity).where(
                Entity.entity_type == entity_type,
                Entity.normalized_name == normalized_name,
            )
        ).scalar_one_or_none()
        if entity is None:
            entity = Entity(
                id=uuid4().hex,
                canonical_name=canonical_name,
                normalized_name=normalized_name,
                entity_type=entity_type,
                info=metadata or {},
            )
        alias = detected.text if normalized != normalized_name else None
        return CanonicalMatch(entity=entity, alias_to_add=alias, alias_source="fuzzy")

    @staticmethod
    def _normalize(value: str) -> str:
        return value.casefold().strip()

    @staticmethod
    def _strip_non_alnum(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value)

    @staticmethod
    def _context_hint(detected: DetectedEntity) -> Optional[str]:
        metadata = detected.metadata or {}
        for key in ("portfolio", "title", "ministry"):
            hint = metadata.get(key)
            if isinstance(hint, str) and hint.strip():
                return hint.casefold()
        return None

    @staticmethod
    def _context_bonus(context_hint: str, metadata: Optional[dict]) -> float:
        if not metadata:
            return 0.0
        for value in metadata.values():
            if isinstance(value, str) and context_hint in value.casefold():
                return 0.05
        return 0.0
