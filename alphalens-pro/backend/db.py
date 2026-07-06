"""SQLAlchemy-Engine und Session-Fabrik (SQLite, WAL-Modus)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.settings import db_path


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine(url: str | None = None) -> Engine:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_engine(url or f"sqlite:///{db_path()}", future=True)

        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def init_db(url: str | None = None) -> Engine:
    """Erzeugt alle Tabellen (idempotent). Alembic-Migrationen folgen, sobald sich das Schema
    nach dem ersten Release ändert — bis dahin ist create_all für die Greenfield-DB korrekt."""
    from backend import models  # noqa: F401  (Modelle registrieren)

    engine = get_engine(url)
    Base.metadata.create_all(engine)
    return engine


@contextmanager
def session_scope() -> Iterator[Session]:
    init_db()
    assert _session_factory is not None
    session = _session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_for_tests(url: str) -> None:
    """Nur für Tests: Engine auf eine In-Memory-/Temp-DB umbiegen."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
    init_db(url)
