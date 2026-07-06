"""Integration test setup: real dockerized Postgres (docker-compose, host port 5433).

Uses a dedicated `agentlens_test` database (dropped and recreated per session,
migrated via Alembic) so tests never touch dev data; tables are truncated
between tests.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlmodel import Session, text

SERVER_DIR = Path(__file__).resolve().parents[1]
PG = "postgresql://agentlens:agentlens@localhost:5433"
TEST_DATABASE_URL = f"{PG.replace('postgresql://', 'postgresql+psycopg://')}/agentlens_test"

TEST_API_KEY = "test-api-key"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    with psycopg.connect(f"{PG}/agentlens", autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS agentlens_test WITH (FORCE)")
        conn.execute("CREATE DATABASE agentlens_test")

    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    command.upgrade(Config(str(SERVER_DIR / "alembic.ini")), "head")

    from app.db import get_engine

    get_engine.cache_clear()
    yield
    get_engine().dispose()


@pytest.fixture
def session(test_database):
    from app.db import get_engine

    with Session(get_engine()) as s:
        yield s


@pytest.fixture(autouse=True)
def clean_tables(session):
    session.execute(text("TRUNCATE llm_call, span, run, project"))
    session.commit()


@pytest.fixture
def project(session, clean_tables):
    from app.api.ingest import hash_api_key
    from app.models import Project

    p = Project(
        name="fittrack-recipes",
        api_key_hash=hash_api_key(TEST_API_KEY),
        created_at=datetime.now(timezone.utc),
    )
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


@pytest.fixture
def client(test_database):
    from app.main import app

    return TestClient(app)
