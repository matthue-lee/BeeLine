from __future__ import annotations

import pytest
from pydantic import ValidationError

from beeline_ingestor.queues.payloads import (
    SummarizeJobPayload,
    VerifyJobPayload,
    EmbedJobPayload,
    LinkJobPayload,
    EntityExtractJobPayload,
)


def test_summarize_payload_defaults_priority() -> None:
    payload = SummarizeJobPayload(release_id="rel-1", idempotency_token="tok-1")
    assert payload.release_id == "rel-1"
    assert payload.priority == 0


def test_summarize_payload_missing_release_id() -> None:
    with pytest.raises(ValidationError):
        SummarizeJobPayload(idempotency_token="tok-2")  # type: ignore[arg-type]


def test_verify_payload_requires_claims() -> None:
    payload = VerifyJobPayload(
        summary_id="sum-1",
        release_id="rel-1",
        claim_batch=["Claim A"],
        idempotency_token="tok-3",
    )
    assert payload.claim_batch == ["Claim A"]

    with pytest.raises(ValidationError):
        VerifyJobPayload(
            summary_id="sum-1",
            release_id="rel-1",
            claim_batch=[],
            idempotency_token="tok-3",
        )


def test_embed_payload_requires_source_type() -> None:
    payload = EmbedJobPayload(
        source_type="release",
        source_id="rel-2",
        text_hash="abc",
        idempotency_token="tok-4",
    )
    assert payload.source_type == "release"

    with pytest.raises(ValidationError):
        EmbedJobPayload(
            source_type="unknown",  # type: ignore[arg-type]
            source_id="rel-2",
            text_hash="abc",
            idempotency_token="tok-4",
        )


def test_link_payload_requires_candidates() -> None:
    payload = LinkJobPayload(
        release_id="rel-3",
        candidate_article_ids=["art-1", "art-2"],
        idempotency_token="tok-5",
    )
    assert len(payload.candidate_article_ids) == 2

    with pytest.raises(ValidationError):
        LinkJobPayload(
            release_id="rel-3",
            candidate_article_ids=[],
            idempotency_token="tok-5",
        )


def test_entity_extract_payload_requires_valid_source() -> None:
    payload = EntityExtractJobPayload(
        source_type="summary",
        source_id="sum-9",
        idempotency_token="tok-9",
    )
    assert payload.source_type == "summary"

    with pytest.raises(ValidationError):
        EntityExtractJobPayload(
            source_type="invalid",  # type: ignore[arg-type]
            source_id="sum-9",
            idempotency_token="tok-9",
        )
