"""Deterministic entity detectors for NZ-specific content."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List

from .datatypes import DetectedEntity, EntityType
from .resources_loader import NamedResource


@dataclass(slots=True)
class DetectorConfig:
    label: EntityType
    confidence: float
    name: str


class BaseDetector:
    """Base class for all deterministic detectors."""

    def __init__(self, config: DetectorConfig):
        self.config = config

    def detect(self, text: str) -> list[DetectedEntity]:  # pragma: no cover - implemented by subclasses
        raise NotImplementedError


class DictionaryDetector(BaseDetector):
    """Detect entities based on curated dictionaries of names/aliases."""

    def __init__(self, config: DetectorConfig, resources: Iterable[NamedResource]):
        super().__init__(config)
        self.lookup: dict[str, dict] = {}
        tokens: list[str] = []
        for entry in resources:
            metadata = {"canonical_name": entry.name}
            metadata.update(entry.metadata)
            for value in [entry.name, *entry.aliases]:
                key = value.casefold()
                if not key:
                    continue
                self.lookup[key] = metadata
                tokens.append(re.escape(value))
        if tokens:
            tokens.sort(key=len, reverse=True)
            pattern = rf"(?<!\w)(?:{'|'.join(tokens)})(?!\w)"
        else:
            pattern = r"a^"  # never matches
        self.pattern = re.compile(pattern, re.IGNORECASE | re.UNICODE)

    def detect(self, text: str) -> list[DetectedEntity]:
        matches: list[DetectedEntity] = []
        for match in self.pattern.finditer(text):
            matched_text = match.group(0)
            entry = self.lookup.get(matched_text.casefold())
            metadata = dict(entry or {})
            metadata["matched_text"] = matched_text
            matches.append(
                DetectedEntity(
                    text=metadata.get("canonical_name", matched_text),
                    start=match.start(),
                    end=match.end(),
                    label=self.config.label,
                    confidence=self.config.confidence,
                    detector=self.config.name,
                    metadata=metadata,
                )
            )
        return matches


class RegexDetector(BaseDetector):
    """Detect entities via custom regex expressions."""

    def __init__(self, config: DetectorConfig, expressions: Iterable[str]):
        super().__init__(config)
        expr_list = [expr for expr in expressions if expr]
        if expr_list:
            union = "|".join(expr_list)
        else:
            union = r"a^"
        self.pattern = re.compile(union, re.IGNORECASE | re.UNICODE)

    def detect(self, text: str) -> list[DetectedEntity]:
        matches: list[DetectedEntity] = []
        for match in self.pattern.finditer(text):
            matches.append(
                DetectedEntity(
                    text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    label=self.config.label,
                    confidence=self.config.confidence,
                    detector=self.config.name,
                    metadata={},
                )
            )
        return matches


class MinisterTitleDetector(BaseDetector):
    """Detected titled phrases like "Minister of Health"."""

    TITLE_PATTERN = re.compile(
        r"\b(?:(?:Associate|Acting)\s+)?Minister\s+(?:for|of)\s+[A-ZĀ-Ū][\w\s\-\&’']+",
        re.UNICODE,
    )
    PRIME_MINISTER_PATTERN = re.compile(r"\bPrime Minister\b", re.IGNORECASE)

    def detect(self, text: str) -> list[DetectedEntity]:
        matches = []
        for pattern in (self.TITLE_PATTERN, self.PRIME_MINISTER_PATTERN):
            for match in pattern.finditer(text):
                matches.append(
                    DetectedEntity(
                        text=match.group(0),
                        start=match.start(),
                        end=match.end(),
                        label=self.config.label,
                        confidence=self.config.confidence,
                        detector=self.config.name,
                        metadata={"title": match.group(0)},
                    )
                )
        return matches
