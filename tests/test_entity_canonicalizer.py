import pathlib
import sys

from sqlalchemy import select

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from beeline_ingestor.config import AppConfig
from beeline_ingestor.db import Database
from beeline_ingestor.entity_extraction import EntityCanonicalizer, EntityExtractionConfig, EntityType
from beeline_ingestor.entity_extraction.datatypes import DetectedEntity
from beeline_ingestor.entity_extraction.store import EntityStore
from beeline_ingestor.models import Entity, EntityAlias


def make_database() -> Database:
    config = AppConfig()
    config.database.uri = "sqlite://"
    database = Database(config)
    database.create_all()
    return database


def make_store(database: Database) -> EntityStore:
    canonicalizer = EntityCanonicalizer(EntityExtractionConfig())
    return EntityStore(database, canonicalizer=canonicalizer)


def make_entity(text: str, label: EntityType, metadata: dict | None = None) -> DetectedEntity:
    return DetectedEntity(
        text=text,
        start=0,
        end=len(text),
        label=label,
        confidence=0.98,
        detector="test",
        metadata=metadata or {},
    )


def test_authority_alias_is_linked_to_canonical_entity():
    database = make_database()
    store = make_store(database)

    detected = make_entity("PM Luxon", EntityType.PERSON, {"title": "Prime Minister"})
    store.persist("rel-1", "release", "PM Luxon met stakeholders", [detected])

    with database.session() as session:
        entities = session.execute(select(Entity)).scalars().all()
        assert len(entities) == 1
        entity = entities[0]
        assert entity.canonical_name == "Christopher Luxon"
        assert entity.verified is True

        alias = session.execute(select(EntityAlias)).scalar_one()
        assert alias.alias == "PM Luxon"


def test_fuzzy_matching_reuses_existing_entity():
    database = make_database()
    store = make_store(database)

    first = make_entity("Christopher Luxon", EntityType.PERSON)
    store.persist("rel-1", "release", "Christopher Luxon statement", [first])

    typo = make_entity("Christpher Laxon", EntityType.PERSON)
    store.persist("rel-2", "release", "Christpher Laxon comment", [typo])

    with database.session() as session:
        entities = session.execute(select(Entity)).scalars().all()
        assert len(entities) == 1
        entity = entities[0]
        assert entity.mention_count == 2
        aliases = session.execute(select(EntityAlias)).scalars().all()
        texts = {alias.alias for alias in aliases}
        assert "Christpher Laxon" in texts


def test_unmatched_entity_creates_new_record():
    database = make_database()
    store = make_store(database)

    detected = make_entity("Future Growth Initiative", EntityType.POLICY, {"portfolio": "Economic"})
    store.persist("rel-3", "release", "Future Growth Initiative launched", [detected])

    with database.session() as session:
        entity = session.execute(select(Entity)).scalar_one()
        assert entity.canonical_name == "Future Growth Initiative"
        assert entity.verified is False
