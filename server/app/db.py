import os
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine
from sqlmodel import Session, create_engine

DEFAULT_DATABASE_URL = "postgresql+psycopg://agentlens:agentlens@localhost:5433/agentlens"


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
