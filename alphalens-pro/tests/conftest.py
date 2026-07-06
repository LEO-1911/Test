from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db import Base


@pytest.fixture()
def session() -> Iterator[Session]:
    """Frische In-Memory-DB pro Test — unabhängig von der globalen Engine."""
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    sess = factory()
    try:
        yield sess
        sess.commit()
    finally:
        sess.close()
