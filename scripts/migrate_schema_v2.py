"""One-off schema migration to extend BeeLine database while preserving data."""
from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("db/beeline.db")


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = conn.execute(f"PRAGMA table_info('{table}')")
    return any(row[1] == column for row in cursor.fetchall())


def index_exists(conn: sqlite3.Connection, name: str) -> bool:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('index', 'trigger') AND name = ?",
        (name,),
    )
    return cursor.fetchone() is not None


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cursor.fetchone() is not None


def create_table(conn: sqlite3.Connection, sql: str) -> None:
    conn.execute(sql)


def migrate() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    # ingestion_runs columns and indexes
    if not column_exists(conn, "ingestion_runs", "source"):
        conn.execute("ALTER TABLE ingestion_runs ADD COLUMN source VARCHAR(32)")
    if not column_exists(conn, "ingestion_runs", "status"):
        conn.execute("ALTER TABLE ingestion_runs ADD COLUMN status VARCHAR(16)")
        conn.execute("UPDATE ingestion_runs SET status='completed' WHERE finished_at IS NOT NULL")
    if not index_exists(conn, "idx_ingestion_runs_started"):
        conn.execute("CREATE INDEX idx_ingestion_runs_started ON ingestion_runs(started_at DESC)")
    if not index_exists(conn, "idx_ingestion_runs_status"):
        conn.execute("CREATE INDEX idx_ingestion_runs_status ON ingestion_runs(status, started_at DESC)")

    # releases columns
    releases_new_columns = {
        "created_at": "ALTER TABLE releases ADD COLUMN created_at DATETIME",
        "updated_at": "ALTER TABLE releases ADD COLUMN updated_at DATETIME",
        "deleted_at": "ALTER TABLE releases ADD COLUMN deleted_at DATETIME",
        "version": "ALTER TABLE releases ADD COLUMN version INTEGER",
        "superseded_by": "ALTER TABLE releases ADD COLUMN superseded_by VARCHAR(128) REFERENCES releases(id)",
    }
    for column, stmt in releases_new_columns.items():
        if not column_exists(conn, "releases", column):
            conn.execute(stmt)
    conn.execute("UPDATE releases SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    conn.execute("UPDATE releases SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    conn.execute("UPDATE releases SET version = COALESCE(version, 1)")

    # releases indexes
    release_indexes = {
        "idx_releases_published": "CREATE INDEX idx_releases_published ON releases(published_at DESC)",
        "idx_releases_portfolio_published": "CREATE INDEX idx_releases_portfolio_published ON releases(portfolio, published_at DESC)",
        "idx_releases_minister_published": "CREATE INDEX idx_releases_minister_published ON releases(minister, published_at DESC)",
        "idx_releases_status": "CREATE INDEX idx_releases_status ON releases(status, published_at DESC)",
    }
    for name, stmt in release_indexes.items():
        if not index_exists(conn, name):
            conn.execute(stmt)

    # news_articles columns
    news_columns = {
        "created_at": "ALTER TABLE news_articles ADD COLUMN created_at DATETIME",
        "updated_at": "ALTER TABLE news_articles ADD COLUMN updated_at DATETIME",
        "author": "ALTER TABLE news_articles ADD COLUMN author VARCHAR",
        "categories": "ALTER TABLE news_articles ADD COLUMN categories JSON",
        "language": "ALTER TABLE news_articles ADD COLUMN language VARCHAR(16)",
        "source_category": "ALTER TABLE news_articles ADD COLUMN source_category VARCHAR",
    }
    for column, stmt in news_columns.items():
        if not column_exists(conn, "news_articles", column):
            conn.execute(stmt)
    conn.execute("UPDATE news_articles SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    conn.execute("UPDATE news_articles SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")

    # release_article_links columns and indexes
    ral_columns = {
        "verified": "ALTER TABLE release_article_links ADD COLUMN verified BOOLEAN DEFAULT 0",
        "verification_score": "ALTER TABLE release_article_links ADD COLUMN verification_score FLOAT",
        "link_type": "ALTER TABLE release_article_links ADD COLUMN link_type VARCHAR(32)",
        "stance": "ALTER TABLE release_article_links ADD COLUMN stance VARCHAR(16)",
        "stance_confidence": "ALTER TABLE release_article_links ADD COLUMN stance_confidence FLOAT",
    }
    for column, stmt in ral_columns.items():
        if not column_exists(conn, "release_article_links", column):
            conn.execute(stmt)
    if not index_exists(conn, "idx_article_release_similarity"):
        conn.execute("CREATE INDEX idx_article_release_similarity ON release_article_links(article_id, similarity DESC)")

    # entities columns
    entity_columns = {
        "canonical_id": "ALTER TABLE entities ADD COLUMN canonical_id VARCHAR(64) REFERENCES entities(id)",
        "created_at": "ALTER TABLE entities ADD COLUMN created_at DATETIME",
        "updated_at": "ALTER TABLE entities ADD COLUMN updated_at DATETIME",
        "verified": "ALTER TABLE entities ADD COLUMN verified BOOLEAN DEFAULT 0",
    }
    for column, stmt in entity_columns.items():
        if not column_exists(conn, "entities", column):
            conn.execute(stmt)
    conn.execute("UPDATE entities SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)")
    conn.execute("UPDATE entities SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)")
    if not index_exists(conn, "idx_entities_type_mentions"):
        conn.execute("CREATE INDEX idx_entities_type_mentions ON entities(entity_type, mention_count DESC)")
    if not index_exists(conn, "idx_entities_last_seen"):
        conn.execute("CREATE INDEX idx_entities_last_seen ON entities(last_seen DESC)")
    if not index_exists(conn, "idx_entities_canonical"):
        conn.execute("CREATE INDEX idx_entities_canonical ON entities(canonical_id)")

    # entity_mentions indexes
    if not index_exists(conn, "idx_entity_mentions_entity_created"):
        conn.execute("CREATE INDEX idx_entity_mentions_entity_created ON entity_mentions(entity_id, created_at DESC)")
    if not index_exists(conn, "idx_entity_mentions_created"):
        conn.execute("CREATE INDEX idx_entity_mentions_created ON entity_mentions(created_at DESC)")

    # new tables
    tables_sql = {
        "entity_aliases": """
            CREATE TABLE IF NOT EXISTS entity_aliases (
                entity_id VARCHAR(64) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                alias VARCHAR NOT NULL,
                normalized_alias VARCHAR NOT NULL,
                source VARCHAR(32),
                confidence FLOAT DEFAULT 1.0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (entity_id, normalized_alias)
            );
        """,
        "entity_cooccurrences": """
            CREATE TABLE IF NOT EXISTS entity_cooccurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_a_id VARCHAR(64) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                entity_b_id VARCHAR(64) NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                cooccurrence_count INTEGER NOT NULL DEFAULT 1,
                relationship_type VARCHAR(32),
                last_seen DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                CHECK (entity_a_id < entity_b_id),
                UNIQUE(entity_a_id, entity_b_id)
            );
        """,
        "entity_cooccurrence_documents": """
            CREATE TABLE IF NOT EXISTS entity_cooccurrence_documents (
                cooccurrence_id INTEGER NOT NULL REFERENCES entity_cooccurrences(id) ON DELETE CASCADE,
                source_type VARCHAR(32) NOT NULL,
                source_id VARCHAR(128) NOT NULL,
                proximity VARCHAR(16),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (cooccurrence_id, source_type, source_id)
            );
        """,
        "entity_statistics": """
            CREATE TABLE IF NOT EXISTS entity_statistics (
                entity_id VARCHAR(64) PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
                mentions_total INTEGER NOT NULL DEFAULT 0,
                mentions_last_7d INTEGER NOT NULL DEFAULT 0,
                mentions_last_30d INTEGER NOT NULL DEFAULT 0,
                top_cooccurrences JSON,
                mentions_by_month JSON,
                last_computed DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "job_runs": """
            CREATE TABLE IF NOT EXISTS job_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_type VARCHAR(64) NOT NULL,
                stage VARCHAR(32),
                release_id VARCHAR(128) REFERENCES releases(id) ON DELETE SET NULL,
                article_id VARCHAR(128) REFERENCES news_articles(id) ON DELETE SET NULL,
                priority INTEGER NOT NULL DEFAULT 0,
                trigger_job_id INTEGER REFERENCES job_runs(id) ON DELETE SET NULL,
                status VARCHAR(16) NOT NULL,
                params JSON,
                result JSON,
                error_message TEXT,
                started_at DATETIME NOT NULL,
                finished_at DATETIME,
                duration_ms INTEGER
            );
        """,
        "failed_jobs": """
            CREATE TABLE IF NOT EXISTS failed_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_run_id INTEGER REFERENCES job_runs(id) ON DELETE SET NULL,
                job_type VARCHAR(64) NOT NULL,
                stage VARCHAR(32),
                release_id VARCHAR(128) REFERENCES releases(id) ON DELETE SET NULL,
                payload JSON NOT NULL,
                payload_snapshot JSON,
                bullmq_job_id VARCHAR(128),
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,
                next_retry_at DATETIME,
                failed_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "llm_calls": """
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_run_id INTEGER REFERENCES job_runs(id) ON DELETE SET NULL,
                model VARCHAR(64) NOT NULL,
                operation VARCHAR(64) NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost_usd FLOAT NOT NULL,
                latency_ms INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "daily_costs": """
            CREATE TABLE IF NOT EXISTS daily_costs (
                date DATE NOT NULL,
                operation VARCHAR(64) NOT NULL,
                total_calls INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                total_cost_usd FLOAT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (date, operation)
            );
        """,
        "content_flags": """
            CREATE TABLE IF NOT EXISTS content_flags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type VARCHAR(32) NOT NULL,
                source_id VARCHAR(128) NOT NULL,
                flag_type VARCHAR(64) NOT NULL,
                severity VARCHAR(16),
                details JSON,
                resolved BOOLEAN DEFAULT 0,
                resolved_by VARCHAR(64),
                resolved_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """,
        "summaries": """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                release_id VARCHAR(128) NOT NULL REFERENCES releases(id) ON DELETE CASCADE,
                summary_short TEXT NOT NULL,
                summary_why_matters TEXT,
                claims JSON,
                model VARCHAR(64) NOT NULL,
                prompt_version VARCHAR(16),
                verification_score FLOAT,
                tokens_used INTEGER,
                cost_usd FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(release_id)
            );
        """,
    }

    for name, stmt in tables_sql.items():
        if not table_exists(conn, name):
            create_table(conn, stmt)

    # indexes for new tables
    if not index_exists(conn, "idx_entity_aliases_lookup"):
        conn.execute("CREATE INDEX idx_entity_aliases_lookup ON entity_aliases(normalized_alias)")
    if not index_exists(conn, "idx_cooccur_count"):
        conn.execute(
            "CREATE INDEX idx_cooccur_count ON entity_cooccurrences(cooccurrence_count DESC)"
        )
    if not index_exists(conn, "idx_job_runs_type_status"):
        conn.execute("CREATE INDEX idx_job_runs_type_status ON job_runs(job_type, status, started_at DESC)")
    if not index_exists(conn, "idx_failed_jobs_retry"):
        conn.execute(
            "CREATE INDEX idx_failed_jobs_retry ON failed_jobs(next_retry_at) WHERE retry_count < max_retries"
        )
    if not index_exists(conn, "idx_llm_calls_operation"):
        conn.execute(
            "CREATE INDEX idx_llm_calls_operation ON llm_calls(operation, created_at DESC)"
        )
    if not index_exists(conn, "idx_content_flags_active"):
        conn.execute(
            "CREATE INDEX idx_content_flags_active ON content_flags(resolved, severity, created_at) WHERE resolved = 0"
        )

    # full-text search for releases and news articles
    if not table_exists(conn, "releases_fts"):
        conn.execute(
            "CREATE VIRTUAL TABLE releases_fts USING fts5(id UNINDEXED, title, text_clean, content='releases', content_rowid='rowid')"
        )
        conn.execute(
            "INSERT INTO releases_fts(rowid, id, title, text_clean) SELECT rowid, id, title, text_clean FROM releases"
        )
    if not index_exists(conn, "releases_fts_insert"):
        conn.executescript(
            """
            CREATE TRIGGER releases_fts_insert AFTER INSERT ON releases BEGIN
                INSERT INTO releases_fts(rowid, id, title, text_clean)
                VALUES (new.rowid, new.id, new.title, new.text_clean);
            END;
            CREATE TRIGGER releases_fts_delete AFTER DELETE ON releases BEGIN
                DELETE FROM releases_fts WHERE rowid = old.rowid;
            END;
            CREATE TRIGGER releases_fts_update AFTER UPDATE ON releases BEGIN
                UPDATE releases_fts SET title = new.title, text_clean = new.text_clean WHERE rowid = new.rowid;
            END;
            """
        )

    if not table_exists(conn, "news_articles_fts"):
        conn.execute(
            "CREATE VIRTUAL TABLE news_articles_fts USING fts5(id UNINDEXED, title, text_clean, content='news_articles', content_rowid='rowid')"
        )
        conn.execute(
            "INSERT INTO news_articles_fts(rowid, id, title, text_clean) SELECT rowid, id, title, text_clean FROM news_articles"
        )
    if not index_exists(conn, "news_articles_fts_insert"):
        conn.executescript(
            """
            CREATE TRIGGER news_articles_fts_insert AFTER INSERT ON news_articles BEGIN
                INSERT INTO news_articles_fts(rowid, id, title, text_clean)
                VALUES (new.rowid, new.id, new.title, new.text_clean);
            END;
            CREATE TRIGGER news_articles_fts_delete AFTER DELETE ON news_articles BEGIN
                DELETE FROM news_articles_fts WHERE rowid = old.rowid;
            END;
            CREATE TRIGGER news_articles_fts_update AFTER UPDATE ON news_articles BEGIN
                UPDATE news_articles_fts SET title = new.title, text_clean = new.text_clean WHERE rowid = new.rowid;
            END;
            """
        )

    conn.commit()
    conn.close()
    print("Schema migration complete")


if __name__ == "__main__":
    migrate()
