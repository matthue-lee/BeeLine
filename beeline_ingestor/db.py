"""Database session and model helpers using SQLAlchemy."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import AppConfig

Base = declarative_base()


def create_engine_from_config(config: AppConfig):
    """Create a SQLAlchemy engine using the provided configuration."""

    url = make_url(config.database.uri)
    if url.get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            return create_engine(
                config.database.uri,
                echo=config.database.echo,
                future=True,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(
            config.database.uri,
            echo=config.database.echo,
            future=True,
            connect_args=connect_args,
        )
    return create_engine(config.database.uri, echo=config.database.echo, future=True)


class Database:
    """Lightweight database helper for managing sessions."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.engine = create_engine_from_config(config)
        self._session_factory = sessionmaker(bind=self.engine, class_=Session, expire_on_commit=False, future=True)

    def create_all(self) -> None:
        """Create database tables if they do not exist."""

        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Provide a transactional scope for database operations."""

        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:  # pragma: no cover - defensive rollback path
            session.rollback()
            raise
        finally:
            session.close()
