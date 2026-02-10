"""Prompt template selection utilities."""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional

from sqlalchemy import select

from .db import Database
from .models import PromptTemplate


@dataclass(slots=True)
class TemplateChoice:
    name: str
    version: str
    body: str
    metadata: dict


class PromptTemplateRepository:
    """Helper for loading prompt templates from the database."""

    def __init__(self, database: Database):
        self.database = database

    def list_templates(self, name: Optional[str] = None) -> list[PromptTemplate]:
        with self.database.session() as session:
            stmt = select(PromptTemplate)
            if name:
                stmt = stmt.where(PromptTemplate.name == name)
            stmt = stmt.order_by(PromptTemplate.name, PromptTemplate.version)
            return session.execute(stmt).scalars().all()

    def active_templates(self, name: str) -> list[PromptTemplate]:
        with self.database.session() as session:
            stmt = (
                select(PromptTemplate)
                .where(PromptTemplate.name == name, PromptTemplate.is_active.is_(True))
                .order_by(PromptTemplate.version)
            )
            return session.execute(stmt).scalars().all()

    def choose_active(self, name: str) -> PromptTemplate:
        templates = self.active_templates(name)
        if not templates:
            raise RuntimeError(f"No active prompt templates found for {name}")
        total_weight = sum(max(t.traffic_allocation or 0, 1) for t in templates)
        pick = random.randint(1, total_weight)
        cumulative = 0
        for template in templates:
            weight = max(template.traffic_allocation or 0, 1)
            cumulative += weight
            if pick <= cumulative:
                return template
        return templates[-1]
