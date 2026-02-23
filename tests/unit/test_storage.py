from datetime import datetime, timezone
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.ingestion.cleaner import CleanResult
from beeline_ingestor.ingestion.fetcher import FetchResult
from beeline_ingestor.ingestion.rss import FeedEntry
from beeline_ingestor.ingestion.storage import ReleaseRepository
from beeline_ingestor.models import DocumentStatus
from beeline_ingestor.utils import compute_canonical_id


def make_config(tmp_path):
    config = AppConfig()
    config.database.uri = f"sqlite+pysqlite:///{tmp_path}/test.db"
    config.database.echo = False
    config.min_content_length = 10
    return config


def test_repository_sets_status_ok(tmp_path):
    config = make_config(tmp_path)
    database = Database(config)
    database.create_all()
    repo = ReleaseRepository(database, config)

    entry = FeedEntry(
        id=compute_canonical_id("Test Title", "https://example.com"),
        title="Test Title",
        url="https://example.com",
        published_at=datetime.now(timezone.utc),
        categories=["Category"],
        summary=None,
        feed_url="https://feed",
    )
    fetch = FetchResult(
        url=entry.url,
        final_url=entry.url,
        status_code=200,
        fetched_at=datetime.now(timezone.utc),
        content="<p>" + "word " * 50 + "</p>",
    )
    cleaned = CleanResult(
        text="word " * 50,
        word_count=50,
        removed_sections=["div.share"],
        excerpt="word",
        metadata={"ministers": ["Hon Example"], "tags": ["Economy"]},
    )

    document, inserted = repo.upsert(entry, fetch, cleaned)

    assert inserted is True
    assert document.status == DocumentStatus.OK
    assert document.word_count == 50
    assert document.provenance["clean_word_count"] == 50
    assert document.provenance.get("cleaner_removed_sections") == ["div.share"]
    assert document.provenance.get("page_ministers") == ["Hon Example"]
    assert document.provenance.get("page_tags") == ["Economy"]
    assert document.minister == "Hon Example"
    assert document.ministers == ["Hon Example"]


def test_repository_partial_when_summary_only(tmp_path):
    config = make_config(tmp_path)
    database = Database(config)
    database.create_all()
    repo = ReleaseRepository(database, config)

    entry = FeedEntry(
        id=compute_canonical_id("Another", "https://example.com/2"),
        title="Another",
        url="https://example.com/2",
        published_at=datetime.now(timezone.utc),
        categories=[],
        summary="Short summary text",
        feed_url="https://feed",
    )
    cleaned = CleanResult(text="Short summary text", word_count=3)

    document, inserted = repo.upsert(entry, None, cleaned)

    assert inserted is True
    assert document.status == DocumentStatus.PARTIAL
    assert document.text_clean == "Short summary text"


def test_repository_partial_when_fetch_blocked(tmp_path):
    config = make_config(tmp_path)
    database = Database(config)
    database.create_all()
    repo = ReleaseRepository(database, config)

    entry = FeedEntry(
        id=compute_canonical_id("Blocked", "https://example.com/3"),
        title="Blocked",
        url="https://example.com/3",
        published_at=datetime.now(timezone.utc),
        categories=[],
        summary="Fallback text",
        feed_url="https://feed",
    )
    fetch = FetchResult(
        url=entry.url,
        final_url=entry.url,
        status_code=403,
        fetched_at=datetime.now(timezone.utc),
        content=None,
        error="blocked",
    )
    cleaned = CleanResult(text="Fallback text", word_count=2)

    document, inserted = repo.upsert(entry, fetch, cleaned)

    assert inserted is True
    assert document.status == DocumentStatus.PARTIAL
    assert document.provenance.get("article_error") == "blocked"


def test_repository_marks_empty_parse(tmp_path):
    config = make_config(tmp_path)
    database = Database(config)
    database.create_all()
    repo = ReleaseRepository(database, config)

    entry = FeedEntry(
        id=compute_canonical_id("Empty", "https://example.com/4"),
        title="Empty",
        url="https://example.com/4",
        published_at=datetime.now(timezone.utc),
        categories=[],
        summary=None,
        feed_url="https://feed",
    )
    fetch = FetchResult(
        url=entry.url,
        final_url=entry.url,
        status_code=200,
        fetched_at=datetime.now(timezone.utc),
        content="<html></html>",
    )
    cleaned = CleanResult(text=None, word_count=0)

    document, inserted = repo.upsert(entry, fetch, cleaned)

    assert inserted is True
    assert document.status == DocumentStatus.EMPTY_PARSE
