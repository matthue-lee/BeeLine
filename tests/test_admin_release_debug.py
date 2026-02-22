import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

try:  # pragma: no cover - skip tests when dependency missing
    import pgvector  # type: ignore[unused-ignore]
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("pgvector dependency missing", allow_module_level=True)

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flask import Flask

from beeline_ingestor.admin import AdminAuthService, create_admin_blueprint
from beeline_ingestor.config import AppConfig, SMTPConfig
from beeline_ingestor.db import Database
from beeline_ingestor.models import (
    AdminRole,
    AdminSession,
    AdminUser,
    Claim,
    ClaimVerification,
    DocumentStatus,
    Entity,
    EntityMention,
    JobRun,
    NewsArticle,
    ReleaseArticleLink,
    ReleaseDocument,
    Summary,
)
from beeline_ingestor.emailer import EmailSender


def _make_app() -> tuple:
    config = AppConfig()
    config.database.uri = "sqlite+pysqlite:///:memory:"
    database = Database(config)
    database.create_all()
    email_sender = EmailSender(SMTPConfig())
    auth_service = AdminAuthService(config.admin_auth, database, email_sender=email_sender)
    app = Flask(__name__)
    app.register_blueprint(create_admin_blueprint(auth_service, database))
    app.testing = True
    return app, database


def _seed_release_debug_data(database):
    now = datetime.now(timezone.utc)
    release = ReleaseDocument(
        id="release-123",
        title="Test Release",
        url="https://gov.example/releases/1",
        published_at=now - timedelta(hours=2),
        minister="Sample Minister",
        portfolio="Sample Portfolio",
        categories=["Economy"],
        text_raw="Raw body of the release",
        text_clean="Clean body of the release with enough words.",
        status=DocumentStatus.OK,
        word_count=8,
        fetched_at=now - timedelta(hours=1, minutes=30),
        provenance={"feed_url": "https://feed", "guid": "guid-1"},
        created_at=now - timedelta(hours=1),
        last_updated_at=now - timedelta(minutes=45),
    )
    summary = Summary(
        release_id=release.id,
        summary_short="Short summary",
        summary_why_matters="Why it matters",
        claims=[{"text": "Claim via summary"}],
        model="gpt-test",
        prompt_version="v1",
        verification_score=0.9,
        tokens_used=120,
        cost_usd=0.05,
        raw_response={"debug": True},
    )

    job_run = JobRun(
        job_type="release_ingest",
        status="completed",
        duration_ms=1200,
        started_at=now - timedelta(minutes=5),
        finished_at=now - timedelta(minutes=4, seconds=30),
    )

    article = NewsArticle(
        id="article-1",
        source="NZ Herald",
        title="Article Title",
        url="https://news.example/article",
        published_at=now - timedelta(hours=1, minutes=45),
        summary="Article summary",
        text_clean="Article text sentence one. Second sentence for snippet.",
        fetched_at=now - timedelta(hours=1, minutes=40),
    )
    link = ReleaseArticleLink(
        release_id=release.id,
        article_id=article.id,
        similarity=0.82,
        rationale="Hybrid score: 0.82 (bm25=0.44, vector=0.91)",
        stance="agrees",
        stance_confidence=0.7,
    )

    entity = Entity(
        id="entity-1",
        canonical_name="NZ Government",
        normalized_name="nz government",
        entity_type="ORG",
        info={},
        first_seen=now,
        last_seen=now,
        mention_count=1,
    )
    release_mention = EntityMention(
        id="mention-release",
        entity_id=entity.id,
        source_type="release",
        source_id=release.id,
        text="NZ Government",
        start_offset=0,
        end_offset=13,
        confidence=0.95,
        detector="regex",
    )
    article_mention = EntityMention(
        id="mention-article",
        entity_id=entity.id,
        source_type="article",
        source_id=article.id,
        text="NZ Government",
        start_offset=0,
        end_offset=13,
        confidence=0.9,
        detector="spacy",
    )

    admin_user = AdminUser(
        email="ops@example.com",
        role=AdminRole.OPERATOR,
        is_active=True,
    )
    token = "test-token"

    with database.session() as session:
        session.add(release)
        session.add(summary)
        session.flush()
        claim = Claim(
            summary_id=summary.id,
            claim_index=0,
            text="Claim stored in DB",
            citations=["release-123:1"],
        )
        session.add(claim)
        session.flush()
        verification = ClaimVerification(
            claim_id=claim.id,
            verdict="supported",
            confidence=0.92,
            evidence_sentences=[{"index": 0, "text": "Evidence sentence."}],
        )
        session.add(verification)
        session.add(job_run)
        session.add(article)
        session.add(link)
        session.add(entity)
        session.add(release_mention)
        session.add(article_mention)
        session.add(admin_user)
        session.flush()
        admin_session = AdminSession(
            user_id=admin_user.id,
            token=token,
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
            created_at=now,
        )
        session.add(admin_session)

    return release.id, token


def test_release_debug_endpoint_returns_expected_sections():
    app, database = _make_app()
    client = app.test_client()
    release_id, token = _seed_release_debug_data(database)

    response = client.get(
        f"/api/admin/releases/{release_id}/debug",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["release"]["id"] == release_id
    assert payload["ingestion"]["last_ingest_job"]["job_type"] == "release_ingest"
    assert payload["llm_outputs"]["summary"]["short"] == "Short summary"
    claims = payload["verification"]["claims"]
    assert len(claims) == 1
    assert claims[0]["verification"]["supporting_sentence"] == "Evidence sentence."
    assert payload["entity_snapshot"]["release"][0]["entity_id"] == "entity-1"
    assert payload["cross_links"][0]["article_id"] == "article-1"
    assert payload["fallbacks"]["verification_skipped"] is False


def test_system_overview_endpoint_returns_counters():
    app, database = _make_app()
    client = app.test_client()
    _, token = _seed_release_debug_data(database)

    response = client.get(
        "/api/admin/system/overview",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert "counters" in payload
    assert payload["counters"]["releases_total"] >= 1
