"""spaCy-backed entity extraction pipeline."""
from __future__ import annotations

import logging
from typing import Iterable, List, Sequence, TYPE_CHECKING

try:  # pragma: no cover - optional import for environments without spaCy
    import spacy  # type: ignore
except ImportError:  # pragma: no cover
    spacy = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - typing aid
    from spacy.language import Language
else:
    Language = object

from .config import EntityExtractionConfig
from .datatypes import DetectedEntity, EntityExtractionResult, EntityType, ExtractionJob
from .detectors import BaseDetector, DetectorConfig, DictionaryDetector, MinisterTitleDetector, RegexDetector
from .resources_loader import load_named_resources
from .validator import EntityValidator

logger = logging.getLogger(__name__)


SPACY_LABEL_MAP = {
    "PERSON": EntityType.PERSON,
    "ORG": EntityType.ORGANISATION,
    "GPE": EntityType.GEOGRAPHY,
    "LOC": EntityType.GEOGRAPHY,
    "LAW": EntityType.POLICY,
    "NORP": EntityType.ORGANISATION,
    "FAC": EntityType.GEOGRAPHY,
}


class EntityExtractionService:
    """Coordinates deterministic detectors and spaCy NER."""

    def __init__(self, config: EntityExtractionConfig | None = None, nlp: "Language" | None = None):
        self.config = config or EntityExtractionConfig()
        self.validator = EntityValidator(self.config)
        self.nlp = nlp or self._load_model(self.config.model_name)
        self.detectors = self._build_detectors()

    def _load_model(self, model_name: str) -> Language:
        if spacy is None:  # pragma: no cover - handled at runtime when spaCy missing
            raise RuntimeError(
                "spaCy is not installed. Install dependencies with `pip install -r requirements.txt`"
            )
        try:
            return spacy.load(model_name, exclude=["lemmatizer"])
        except OSError as exc:  # pragma: no cover - depends on runtime env
            raise RuntimeError(
                f"spaCy model '{model_name}' is not installed. "
                "Run `python -m spacy download en_core_web_lg` before starting the worker."
            ) from exc

    def _build_detectors(self) -> list[BaseDetector]:
        resources_dir = self.config.resources_dir
        ministers = load_named_resources(resources_dir / "ministers.json")
        ministries = load_named_resources(resources_dir / "ministries.json")
        geographies = load_named_resources(resources_dir / "geographies.json")
        policies = load_named_resources(resources_dir / "policies.json")

        detectors: list[BaseDetector] = [
            DictionaryDetector(DetectorConfig(EntityType.PERSON, 0.99, "minister-roster"), ministers),
            DictionaryDetector(DetectorConfig(EntityType.MINISTRY, 0.95, "ministry-roster"), ministries),
            DictionaryDetector(DetectorConfig(EntityType.GEOGRAPHY, 0.92, "geography-list"), geographies),
            DictionaryDetector(DetectorConfig(EntityType.POLICY, 0.9, "policy-list"), policies),
            MinisterTitleDetector(DetectorConfig(EntityType.MINISTRY, 0.85, "minister-title")),
        ]

        pattern_expressions: list[str] = []
        for policy in policies:
            patterns = policy.metadata.get("patterns") if policy.metadata else None
            if isinstance(patterns, list):
                pattern_expressions.extend(patterns)
        if pattern_expressions:
            detectors.append(RegexDetector(DetectorConfig(EntityType.POLICY, 0.88, "policy-patterns"), pattern_expressions))
        return detectors

    def run_detectors(self, text: str) -> list[DetectedEntity]:
        matches: list[DetectedEntity] = []
        for detector in self.detectors:
            try:
                matches.extend(detector.detect(text))
            except Exception:  # pragma: no cover - logging path
                logger.exception("Detector %s failed", detector.config.name)
        return matches

    def _map_spacy_label(self, label: str) -> EntityType:
        return SPACY_LABEL_MAP.get(label, EntityType.UNKNOWN)

    def _run_spacy(self, text: str) -> list[DetectedEntity]:
        doc = self.nlp(text)
        entities: list[DetectedEntity] = []
        for ent in doc.ents:
            entity_type = self._map_spacy_label(ent.label_)
            confidence = 0.85 if entity_type != EntityType.UNKNOWN else 0.5
            entities.append(
                DetectedEntity(
                    text=ent.text,
                    start=ent.start_char,
                    end=ent.end_char,
                    label=entity_type,
                    confidence=confidence,
                    detector="spacy",
                    metadata={"spacy_label": ent.label_},
                )
            )
        return entities

    def extract(self, text: str, source_id: str, source_type: str) -> EntityExtractionResult:
        text = (text or "").strip()
        if not text:
            return EntityExtractionResult(
                source_id=source_id,
                source_type=source_type,
                text_length=0,
                entities=[],
                skipped=True,
                notes="empty-text",
            )
        snippet = text[: self.config.max_document_length]
        deterministic = self.run_detectors(snippet)
        spacy_entities = self._run_spacy(snippet)
        combined = [*deterministic, *spacy_entities]
        filtered = self.validator.filter_entities(combined)
        return EntityExtractionResult(
            source_id=source_id,
            source_type=source_type,
            text_length=len(snippet),
            entities=filtered,
            skipped=False,
        )

    def process_jobs(self, jobs: Sequence[ExtractionJob]) -> list[EntityExtractionResult]:
        return [self.extract(job.text, job.source_id, job.source_type) for job in jobs]
