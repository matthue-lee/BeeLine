"""Configuration helpers for entity extraction."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_MODEL = os.getenv("SPACY_ENTITY_MODEL", "en_core_web_lg")


def _default_blocklist() -> list[str]:
    return [
        "government",
        "new zealand",
        "crown",
        "state",
        "week",
        "month",
        "year",
    ]


@dataclass(slots=True)
class EntityExtractionConfig:
    """Runtime options for the entity extraction pipeline."""

    model_name: str = DEFAULT_MODEL
    max_document_length: int = 60_000
    min_entity_length: int = 3
    min_confidence: float = 0.6
    max_workers: int = int(os.getenv("ENTITY_EXTRACTION_WORKERS", "2"))
    blocklist: Sequence[str] = field(default_factory=_default_blocklist)
    _blocklist_set: set[str] = field(init=False, repr=False)
    resources_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent / "resources"
    )

    def __post_init__(self) -> None:
        self._blocklist_set = {entry.lower().strip() for entry in self.blocklist}

    def is_blocklisted(self, value: str) -> bool:
        return value.lower().strip() in self._blocklist_set

    def normalise(self, value: str) -> str:
        return value.strip()

    @property
    def resource_files(self) -> Iterable[Path]:
        return self.resources_dir.glob("*.json")
