import pathlib
import sys

import pytest

spacy = pytest.importorskip("spacy")

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.entity_extraction import (
    EntityExtractionBatchProcessor,
    EntityExtractionConfig,
    EntityExtractionService,
    EntityType,
    ExtractionJob,
)
from beeline_ingestor.entity_extraction.datatypes import DetectedEntity
from beeline_ingestor.entity_extraction.validator import EntityValidator


def make_service() -> EntityExtractionService:
    config = EntityExtractionConfig(model_name="en")
    blank_nlp = spacy.blank("en")
    return EntityExtractionService(config=config, nlp=blank_nlp)


def test_service_detects_minister_from_roster():
    service = make_service()
    text = "Prime Minister Christopher Luxon confirmed support for Te Puni Kōkiri."
    result = service.extract(text, "release-1", "release")
    assert any(entity.text == "Christopher Luxon" and entity.label == EntityType.PERSON for entity in result.entities)
    assert any(entity.label == EntityType.MINISTRY for entity in result.entities)


def test_validator_blocks_blocklisted_terms():
    config = EntityExtractionConfig(blocklist=["government"])
    validator = EntityValidator(config)
    candidate = DetectedEntity(
        text="Government",
        start=0,
        end=10,
        label=EntityType.ORGANISATION,
        confidence=0.99,
        detector="test",
        metadata={},
    )
    assert validator.is_valid(candidate) is False


def test_batch_processor_handles_multiple_jobs():
    service = make_service()
    processor = EntityExtractionBatchProcessor(service=service)
    jobs = [
        ExtractionJob(source_id="release-1", source_type="release", text="Prime Minister Christopher Luxon"),
        ExtractionJob(source_id="release-2", source_type="release", text="Minister of Health Erica Stanford"),
    ]
    results = processor.process(jobs)
    assert {result.source_id for result in results} == {"release-1", "release-2"}
    assert all(result.entities for result in results)
